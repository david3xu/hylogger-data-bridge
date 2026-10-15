// Synchronise committed snapshots over SSE and coordinate retry-safe user actions and host handoffs.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  buildCommittedDecisionNotice,
  deliverAuthoritativeHandoff,
  detectHostCapability,
  type HostCapability,
  type HostDeliveryOutcome,
  type HostDeliveryState,
  type HostTransport,
  notifyCommittedDecision,
  verifyAuthoritativeHandoff,
} from "../host/bridge";
import type { Book, DecisionChoice, Page } from "../state/contracts";
import {
  canDispatchHostHandoff,
  completeSubmission,
  type DecisionDraft,
  failSubmission,
  findHostDelivery,
  followLatest,
  getDraft,
  initialReader,
  isDecisionConfirmed,
  pauseFollowing,
  prepareSubmission,
  type Reader,
  receiveBook,
  recordHostDelivery,
  selectPage,
  setAssessmentDeclined,
  updateDraft,
} from "../state/reader";
import {
  type ConnectionState,
  fetchBookSnapshot,
  postPageDecision,
  postStartDemo,
  subscribeToBookEvents,
} from "./api";

const SESSION_STORAGE_KEY = "hylogger.reader.session.v1";

type PersistedSession = {
  selectedId: string | null;
  following: boolean;
  drafts: Record<string, DecisionDraft>;
  hostDeliveries: Record<string, HostDeliveryState>;
  declinedAssessments: Record<string, boolean>;
};

export function loadPersistedReader(): Reader {
  try {
    if (typeof window === "undefined" || !window.sessionStorage) return initialReader;
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return initialReader;
    const parsed = JSON.parse(raw) as Partial<PersistedSession>;
    const drafts: Record<string, DecisionDraft> = {};
    if (parsed.drafts && typeof parsed.drafts === "object") {
      for (const [key, value] of Object.entries(parsed.drafts)) {
        if (value && typeof value === "object" && typeof value.pageId === "string") {
          drafts[key] = {
            ...value,
            status: value.status === "submitting" ? "failed" : value.status,
          };
        }
      }
    }
    const hostDeliveries: Record<string, HostDeliveryState> = {};
    if (parsed.hostDeliveries && typeof parsed.hostDeliveries === "object") {
      for (const [key, value] of Object.entries(parsed.hostDeliveries)) {
        if (
          value &&
          typeof value === "object" &&
          typeof value.pageId === "string" &&
          typeof value.continuationId === "string"
        ) {
          hostDeliveries[key] = {
            ...value,
            status: value.status === "delivering" ? "failed" : value.status,
          };
        }
      }
    }
    return {
      book: null,
      selectedId: typeof parsed.selectedId === "string" ? parsed.selectedId : null,
      following: typeof parsed.following === "boolean" ? parsed.following : true,
      drafts,
      hostDeliveries,
      declinedAssessments:
        parsed.declinedAssessments && typeof parsed.declinedAssessments === "object"
          ? (parsed.declinedAssessments as Record<string, boolean>)
          : {},
    };
  } catch {
    return initialReader;
  }
}

export function savePersistedReader(reader: Reader): boolean {
  try {
    if (typeof window === "undefined" || !window.sessionStorage) return false;
    const payload: PersistedSession = {
      selectedId: reader.selectedId,
      following: reader.following,
      drafts: reader.drafts,
      hostDeliveries: reader.hostDeliveries,
      declinedAssessments: reader.declinedAssessments,
    };
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(payload));
    return true;
  } catch {
    return false; // Keep editing possible, but never claim that an unsaved draft was saved.
  }
}

export function useBook(hostTransport?: HostTransport) {
  const [reader, setReader] = useState<Reader>(loadPersistedReader);
  const [draftSaveStatus, setDraftSaveStatus] = useState<"saved" | "unavailable" | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [generation, setGeneration] = useState(0);
  const [hostCapability] = useState<HostCapability>(() => detectHostCapability(hostTransport));
  const [lastHostReceipt, setLastHostReceipt] = useState<HostDeliveryOutcome | null>(null);

  const readerRef = useRef(reader);
  readerRef.current = reader;
  const connectionRef = useRef<ConnectionState>(connection);
  connectionRef.current = connection;
  const errorRef = useRef<string | null>(error);
  errorRef.current = error;
  const busyRef = useRef(busy);
  busyRef.current = busy;
  const receiptRef = useRef<HostDeliveryOutcome | null>(lastHostReceipt);
  receiptRef.current = lastHostReceipt;

  const refresh = useRef<() => Promise<Book | null>>(async () => null);

  const updateConnection = useCallback((next: ConnectionState) => {
    connectionRef.current = next;
    setConnection(next);
  }, []);

  const updateError = useCallback((next: string | null) => {
    errorRef.current = next;
    setError(next);
  }, []);

  const updateBusy = useCallback((next: boolean) => {
    busyRef.current = next;
    setBusy(next);
  }, []);

  const updateReceipt = useCallback((next: HostDeliveryOutcome | null) => {
    receiptRef.current = next;
    setLastHostReceipt(next);
  }, []);

  const applyReader = useCallback((updater: (current: Reader) => Reader): Reader => {
    const next = updater(readerRef.current);
    readerRef.current = next;
    setDraftSaveStatus(savePersistedReader(next) ? "saved" : "unavailable");
    setReader(next);
    return next;
  }, []);

  useEffect(() => {
    setDraftSaveStatus(savePersistedReader(reader) ? "saved" : "unavailable");
  }, [reader]);

  const connect = useCallback(
    (reconnect = false): (() => void) => {
      updateConnection(reconnect ? "reconnecting" : "connecting");
      let disposed = false;
      let requested = false;
      let fetching: Promise<Book | null> | null = null;
      let unsubscribeEvents: (() => void) | null = null;
      const abort = new AbortController();

      const fetchBook = (): Promise<Book | null> => {
        requested = true;
        if (fetching) return fetching;
        fetching = (async () => {
          let latestBook: Book | null = null;
          while (requested && !disposed) {
            requested = false;
            try {
              const book = await fetchBookSnapshot(abort.signal);
              latestBook = book;
              if (disposed) return null;
              applyReader((current) => receiveBook(current, book));
              updateError(null);
              if (!unsubscribeEvents) {
                unsubscribeEvents = subscribeToBookEvents(book.sequence, {
                  onOpen: () => {
                    if (!disposed) {
                      updateConnection("live");
                      void fetchBook();
                    }
                  },
                  onError: () => {
                    if (!disposed) {
                      updateConnection("reconnecting");
                    }
                  },
                  onCommittedUpdate: () => {
                    void fetchBook();
                  },
                });
              }
            } catch (failure) {
              if (!disposed) {
                if (!unsubscribeEvents) updateConnection("offline");
                updateError(
                  failure instanceof Error ? failure.message : "The book could not be loaded.",
                );
              }
            }
          }
          return latestBook;
        })().finally(() => {
          fetching = null;
        });
        return fetching;
      };

      refresh.current = fetchBook;
      void fetchBook();

      return () => {
        disposed = true;
        unsubscribeEvents?.();
        abort.abort();
      };
    },
    [applyReader, updateConnection, updateError],
  );

  useEffect(() => {
    return connect(generation > 0);
  }, [connect, generation]);

  const retry = useCallback(() => {
    updateError(null);
    updateConnection("connecting");
    setGeneration((value) => value + 1);
  }, [updateConnection, updateError]);

  const start = useCallback(
    async (page: Page): Promise<boolean> => {
      if (busyRef.current) return false;
      updateBusy(true);
      updateError(null);
      try {
        await postStartDemo(page.id, page.revision);
        await refresh.current();
        return true;
      } catch (failure) {
        await refresh.current();
        updateError(
          failure instanceof Error
            ? failure.message
            : "The request could not be completed. You can retry safely.",
        );
        return false;
      } finally {
        updateBusy(false);
      }
    },
    [updateBusy, updateError],
  );

  const updateDecisionDraft = useCallback(
    (page: Page, choice: DecisionChoice, note: string) => {
      applyReader((current) => updateDraft(current, page, choice, note));
    },
    [applyReader],
  );

  const dispatchHostHandoff = useCallback(
    async (book: Book, lockedPage: Page): Promise<boolean> => {
      const existing = readerRef.current.hostDeliveries[lockedPage.id];
      if (!canDispatchHostHandoff(book, lockedPage.id, existing)) {
        return true;
      }

      const capability = detectHostCapability(hostTransport);
      if (!capability.automaticDispatchAvailable || !hostTransport?.fetchAuthoritativeHandoff) {
        if (hostTransport?.notifyDecisionCommitted) {
          const notice = buildCommittedDecisionNotice(book, lockedPage);
          if (notice) {
            const receipt = await notifyCommittedDecision(notice, hostTransport);
            updateReceipt(receipt);
            return receipt.accepted;
          }
        }
        return true;
      }

      let rawHandoff: unknown;
      try {
        rawHandoff = await hostTransport.fetchAuthoritativeHandoff(lockedPage.id);
      } catch (failure) {
        const detail =
          failure instanceof Error
            ? failure.message
            : "Could not obtain an authoritative handoff from the backend.";
        updateError(detail);
        return false;
      }

      const handoff = verifyAuthoritativeHandoff(book, lockedPage, rawHandoff);
      if (!handoff) {
        return true;
      }

      const deliveringState: HostDeliveryState = {
        pageId: lockedPage.id,
        successorId: handoff.successor_id,
        continuationId: handoff.continuation_id,
        decisionId: handoff.decision_id,
        handoff,
        status: "delivering",
        error: null,
        attempts: handoff.attempt,
      };
      applyReader((current) => recordHostDelivery(current, deliveringState));

      const outcome = await deliverAuthoritativeHandoff(handoff, hostTransport);
      updateReceipt(outcome);

      const finalState: HostDeliveryState = {
        pageId: lockedPage.id,
        successorId: handoff.successor_id,
        continuationId: handoff.continuation_id,
        decisionId: handoff.decision_id,
        handoff,
        status: outcome.accepted ? "accepted" : "failed",
        error: outcome.accepted ? null : outcome.detail,
        attempts: handoff.attempt,
      };
      applyReader((current) => recordHostDelivery(current, finalState));
      if (!outcome.accepted) {
        updateError(outcome.detail);
      }
      return outcome.accepted;
    },
    [applyReader, hostTransport, updateError, updateReceipt],
  );

  const retryHostDelivery = useCallback(
    async (pageId: string): Promise<boolean> => {
      if (busyRef.current) return false;
      const existing = readerRef.current.hostDeliveries[pageId];
      const book = readerRef.current.book;
      const lockedPage = book?.pages.find((item) => item.id === pageId);
      if (!existing || !book || !lockedPage) return false;
      if (!canDispatchHostHandoff(book, pageId, existing)) {
        applyReader((current) => receiveBook(current, book));
        return false;
      }

      updateBusy(true);
      updateError(null);
      try {
        const outcome = await deliverAuthoritativeHandoff(existing.handoff, hostTransport);
        updateReceipt(outcome);
        const updatedState: HostDeliveryState = {
          ...existing,
          status: outcome.accepted ? "accepted" : "failed",
          error: outcome.accepted ? null : outcome.detail,
        };
        applyReader((current) => recordHostDelivery(current, updatedState));
        if (!outcome.accepted) {
          updateError(outcome.detail);
        }
        return outcome.accepted;
      } finally {
        updateBusy(false);
      }
    },
    [applyReader, hostTransport, updateBusy, updateError, updateReceipt],
  );

  const decide = useCallback(
    async (page: Page, choice?: DecisionChoice, note?: string): Promise<boolean> => {
      if (busyRef.current) return false;
      updateBusy(true);
      updateError(null);

      const prepared = prepareSubmission(readerRef.current, page, choice, note);
      applyReader(() => prepared.reader);
      const { draft } = prepared;

      try {
        const snapshot = await postPageDecision(page.id, {
          choice: draft.choice,
          note: draft.note,
          expected_revision: page.revision,
          request_id: draft.requestId,
        });
        if (!isDecisionConfirmed(snapshot, draft)) {
          throw new Error(
            "The service response did not confirm the committed decision. Your input and request ID are preserved for retry.",
          );
        }
        applyReader((current) =>
          completeSubmission(receiveBook(current, snapshot), page.id, draft),
        );
        const lockedPage = snapshot.pages.find((item) => item.id === page.id);
        if (lockedPage) {
          await dispatchHostHandoff(snapshot, lockedPage);
        }
        return true;
      } catch (failure) {
        const message =
          failure instanceof Error
            ? failure.message
            : "The decision could not be saved. Retry safely with the preserved request ID.";
        if (isDecisionConfirmed(readerRef.current.book, draft) && readerRef.current.book) {
          const confirmedBook = readerRef.current.book;
          applyReader((current) => completeSubmission(current, page.id, draft));
          const lockedPage = confirmedBook.pages.find((item) => item.id === page.id);
          if (lockedPage) {
            await dispatchHostHandoff(confirmedBook, lockedPage);
          }
          return true;
        }
        const refreshed = await refresh.current();
        if (refreshed && isDecisionConfirmed(refreshed, draft)) {
          applyReader((current) =>
            completeSubmission(receiveBook(current, refreshed), page.id, draft),
          );
          const lockedPage = refreshed.pages.find((item) => item.id === page.id);
          if (lockedPage) {
            await dispatchHostHandoff(refreshed, lockedPage);
          }
          return true;
        }
        applyReader((current) => failSubmission(current, page.id, message));
        updateError(message);
        return false;
      } finally {
        updateBusy(false);
      }
    },
    [applyReader, dispatchHostHandoff, updateBusy, updateError],
  );

  const getState = useCallback(
    () => ({
      ...readerRef.current,
      connection: connectionRef.current,
      error: errorRef.current,
      busy: busyRef.current,
      hostCapability,
      lastHostReceipt: receiptRef.current,
    }),
    [hostCapability],
  );

  return {
    ...reader,
    draftSaveStatus,
    connection,
    error,
    busy,
    hostCapability,
    lastHostReceipt,
    connect,
    getState,
    retry,
    start,
    decide,
    retryHostDelivery,
    getPageDraft: (page: Page) => getDraft(readerRef.current, page),
    getPageHostDelivery: (page: Page) => findHostDelivery(readerRef.current, page),
    updateDecisionDraft,
    select: (id: string) => applyReader((current) => selectPage(current, id)),
    pause: () => applyReader((current) => pauseFollowing(current)),
    follow: () => applyReader((current) => followLatest(current)),
    setAdviceDeclined: (pageId: string, declined: boolean) =>
      applyReader((current) => setAssessmentDeclined(current, pageId, declined)),
  };
}
