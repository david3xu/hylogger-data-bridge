// Manage reader navigation, paused history reading, retry-safe decision drafts, and host handoffs.
import { type HostDeliveryState, hasBackendContinuationProgressed } from "../host/bridge";
import type { Book, DecisionChoice, Page } from "./contracts";

export type DecisionDraft = {
  pageId: string;
  revision: number;
  choice: DecisionChoice;
  note: string;
  requestId: string;
  signature: string;
  status: "editing" | "submitting" | "failed";
  error: string | null;
};

export type Reader = {
  book: Book | null;
  selectedId: string | null;
  following: boolean;
  drafts: Record<string, DecisionDraft>;
  hostDeliveries: Record<string, HostDeliveryState>;
  declinedAssessments: Record<string, boolean>;
};

export const initialReader: Reader = {
  book: null,
  selectedId: null,
  following: true,
  drafts: {},
  hostDeliveries: {},
  declinedAssessments: {},
};

export function makeSignature(
  pageId: string,
  revision: number,
  choice: DecisionChoice,
  note: string,
): string {
  return JSON.stringify([pageId, revision, choice, note]);
}

function defaultIdFactory(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function isDecisionConfirmed(book: Book | null, draft: DecisionDraft | undefined): boolean {
  if (!book || !draft) return false;
  const page = book.pages.find((item) => item.id === draft.pageId);
  if (!page || page.status !== "locked" || !page.decision) {
    return false;
  }
  if (page.decision.choice !== draft.choice || page.decision.note !== draft.note) {
    return false;
  }
  if (
    page.decision.request_id !== undefined &&
    draft.requestId &&
    page.decision.request_id !== draft.requestId
  ) {
    return false;
  }
  return book.pages.some((item) => item.parent_id === page.id);
}

export function isHostDeliveryObsolete(book: Book, delivery: HostDeliveryState): boolean {
  const page = book.pages.find((item) => item.id === delivery.pageId);
  if (!page || page.status !== "locked" || !page.decision) {
    return true;
  }
  if (hasBackendContinuationProgressed(book, delivery.pageId, delivery.successorId)) {
    return true;
  }
  const continuation = book.continuations?.find(
    (item) => item.page_id === delivery.pageId || item.id === delivery.continuationId,
  );
  if (continuation) {
    if (continuation.state === "running" && delivery.status === "failed") {
      return true;
    }
    if (continuation.attempts > delivery.attempts && delivery.status === "failed") {
      return true;
    }
  }
  return false;
}

export function reconcileHostDeliveries(
  book: Book,
  hostDeliveries: Record<string, HostDeliveryState>,
): Record<string, HostDeliveryState> {
  const next: Record<string, HostDeliveryState> = {};
  for (const [pageId, delivery] of Object.entries(hostDeliveries)) {
    if (!isHostDeliveryObsolete(book, delivery)) {
      next[pageId] = delivery;
    }
  }
  return next;
}

export function canDispatchHostHandoff(
  book: Book | null,
  pageId: string,
  existing?: HostDeliveryState,
): boolean {
  if (!book) return false;
  const page = book.pages.find((item) => item.id === pageId);
  if (!page || page.status !== "locked" || !page.decision) {
    return false;
  }
  if (page.decision.actor?.kind !== "human") {
    return false;
  }
  const continuation = book.continuations?.find((item) => item.page_id === pageId);
  if (!continuation) {
    return false;
  }
  if (hasBackendContinuationProgressed(book, pageId, continuation.successor_id)) {
    return false;
  }
  if (continuation.state !== "pending" && continuation.state !== "running") {
    return false;
  }
  if (existing?.status === "delivering") {
    return false;
  }
  if (
    existing?.status === "accepted" &&
    existing.continuationId === continuation.id &&
    existing.attempts >= Math.max(1, continuation.attempts)
  ) {
    return false;
  }
  return true;
}

export function receiveBook(reader: Reader, book: Book): Reader {
  if (reader.book && book.sequence < reader.book.sequence) {
    return reader;
  }
  const selectionExists = book.pages.some((page) => page.id === reader.selectedId);
  const nextDrafts: Record<string, DecisionDraft> = { ...reader.drafts };
  let confirmedSuccessorId: string | null = null;

  for (const page of book.pages) {
    const existing = nextDrafts[page.id];
    if (!existing) continue;
    if (isDecisionConfirmed(book, existing)) {
      delete nextDrafts[page.id];
      const successor =
        page.decision?.successor_id ??
        book.pages.find((candidate) => candidate.parent_id === page.id)?.id ??
        book.current_page_id;
      confirmedSuccessorId = successor;
    } else if (
      page.status !== "locked" &&
      existing.revision !== page.revision &&
      existing.status !== "submitting"
    ) {
      nextDrafts[page.id] = {
        ...existing,
        revision: page.revision,
      };
    }
  }

  const nextHostDeliveries = reconcileHostDeliveries(book, reader.hostDeliveries);

  if (confirmedSuccessorId !== null) {
    return {
      ...reader,
      book,
      selectedId: confirmedSuccessorId,
      following: confirmedSuccessorId === book.current_page_id,
      drafts: nextDrafts,
      hostDeliveries: nextHostDeliveries,
    };
  }

  return {
    ...reader,
    book,
    selectedId: reader.following || !selectionExists ? book.current_page_id : reader.selectedId,
    drafts: nextDrafts,
    hostDeliveries: nextHostDeliveries,
  };
}

export function selectPage(reader: Reader, id: string): Reader {
  if (!reader.book?.pages.some((page) => page.id === id)) {
    return reader;
  }
  return {
    ...reader,
    selectedId: id,
    following: id === reader.book.current_page_id,
  };
}

export function pauseFollowing(reader: Reader): Reader {
  if (!reader.following) return reader;
  return { ...reader, following: false };
}

export function followLatest(reader: Reader): Reader {
  return {
    ...reader,
    following: true,
    selectedId: reader.book?.current_page_id ?? null,
  };
}

export function getDraft(reader: Reader, page: Page): DecisionDraft {
  const existing = reader.drafts[page.id];
  if (existing) {
    return existing;
  }
  const choice: DecisionChoice = "accept";
  const note = "";
  return {
    pageId: page.id,
    revision: page.revision,
    choice,
    note,
    requestId: "",
    signature: makeSignature(page.id, page.revision, choice, note),
    status: "editing",
    error: null,
  };
}

export function updateDraft(
  reader: Reader,
  page: Page,
  choice: DecisionChoice,
  note: string,
): Reader {
  const existing = getDraft(reader, page);
  const nextSignature = makeSignature(page.id, page.revision, choice, note);
  const preserveRequestId = existing.signature === nextSignature ? existing.requestId : "";
  return {
    ...reader,
    drafts: {
      ...reader.drafts,
      [page.id]: {
        pageId: page.id,
        revision: page.revision,
        choice,
        note,
        requestId: preserveRequestId,
        signature: nextSignature,
        status: "editing",
        error: null,
      },
    },
  };
}

export function prepareSubmission(
  reader: Reader,
  page: Page,
  choice?: DecisionChoice,
  note?: string,
  createId: () => string = defaultIdFactory,
): { reader: Reader; draft: DecisionDraft } {
  const current = getDraft(reader, page);
  const resolvedChoice = choice ?? current.choice;
  const resolvedNote = note ?? current.note;
  const signature = makeSignature(page.id, page.revision, resolvedChoice, resolvedNote);
  const requestId =
    current.signature === signature && current.requestId ? current.requestId : createId();
  const draft: DecisionDraft = {
    pageId: page.id,
    revision: page.revision,
    choice: resolvedChoice,
    note: resolvedNote,
    requestId,
    signature,
    status: "submitting",
    error: null,
  };
  return {
    reader: {
      ...reader,
      drafts: {
        ...reader.drafts,
        [page.id]: draft,
      },
    },
    draft,
  };
}

export function failSubmission(reader: Reader, pageId: string, error: string): Reader {
  const current = reader.drafts[pageId];
  if (!current) return reader;
  return {
    ...reader,
    drafts: {
      ...reader.drafts,
      [pageId]: {
        ...current,
        status: "failed",
        error,
      },
    },
  };
}

export function completeSubmission(
  reader: Reader,
  pageId: string,
  submittedDraft?: DecisionDraft,
): Reader {
  const draftToVerify = reader.drafts[pageId] ?? submittedDraft;
  if (!isDecisionConfirmed(reader.book, draftToVerify)) {
    return failSubmission(
      reader,
      pageId,
      "The service response did not confirm the committed decision. Your input and request ID are preserved for retry.",
    );
  }
  const lockedPage = reader.book?.pages.find((item) => item.id === pageId);
  const successorId =
    lockedPage?.decision?.successor_id ??
    reader.book?.pages.find((item) => item.parent_id === pageId)?.id ??
    reader.book?.current_page_id ??
    null;
  const nextDrafts = { ...reader.drafts };
  delete nextDrafts[pageId];
  return {
    ...reader,
    following: successorId === (reader.book?.current_page_id ?? successorId),
    selectedId: successorId,
    drafts: nextDrafts,
  };
}

export function recordHostDelivery(reader: Reader, delivery: HostDeliveryState): Reader {
  if (reader.book && isHostDeliveryObsolete(reader.book, delivery)) {
    const nextDeliveries = { ...reader.hostDeliveries };
    delete nextDeliveries[delivery.pageId];
    return {
      ...reader,
      hostDeliveries: nextDeliveries,
    };
  }
  return {
    ...reader,
    hostDeliveries: {
      ...reader.hostDeliveries,
      [delivery.pageId]: delivery,
    },
  };
}

export function findHostDelivery(reader: Reader, page: Page): HostDeliveryState | undefined {
  const candidate =
    reader.hostDeliveries[page.id] ??
    Object.values(reader.hostDeliveries).find((item) => item.successorId === page.id);
  if (candidate && reader.book && isHostDeliveryObsolete(reader.book, candidate)) {
    return undefined;
  }
  return candidate;
}

export function setAssessmentDeclined(reader: Reader, pageId: string, declined: boolean): Reader {
  return {
    ...reader,
    declinedAssessments: {
      ...reader.declinedAssessments,
      [pageId]: declined,
    },
  };
}

export function isAssessmentDeclined(reader: Reader, pageId: string): boolean {
  return Boolean(reader.declinedAssessments[pageId]);
}

export function findParentPage(book: Book | null, page: Page): Page | undefined {
  if (!book || !page.parent_id) return undefined;
  return book.pages.find((item) => item.id === page.parent_id);
}

export function findSuccessorPage(book: Book | null, page: Page): Page | undefined {
  if (!book) return undefined;
  return book.pages.find((item) => item.parent_id === page.id);
}
