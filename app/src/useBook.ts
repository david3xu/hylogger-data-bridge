// Synchronise committed snapshots over SSE and submit explicit, retry-safe user actions.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  type DecisionChoice,
  decodeBook,
  followLatest,
  initialReader,
  type Page,
  receiveBook,
  selectPage,
} from "./book";

type Connection = "connecting" | "live" | "reconnecting" | "offline";

async function responseError(response: Response): Promise<Error> {
  let detail = "The local service could not complete this request.";
  try {
    const body = await response.json();
    if (typeof body.error === "string") detail = body.error;
  } catch {
    /* The HTTP status is still useful if a proxy returned non-JSON. */
  }
  if (response.status === 409)
    detail =
      "This page changed. The book has refreshed; review the latest evidence before retrying.";
  return new Error(detail);
}

export function useBook() {
  const [reader, setReader] = useState(initialReader);
  const [connection, setConnection] = useState<Connection>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [generation, setGeneration] = useState(0);
  const refresh = useRef<() => Promise<void>>(async () => {});
  const decisionRequest = useRef<{ signature: string; requestId: string } | null>(null);

  useEffect(() => {
    setConnection(generation > 0 ? "reconnecting" : "connecting");
    let disposed = false;
    let requested = false;
    let fetching: Promise<void> | null = null;
    let events: EventSource | null = null;
    const abort = new AbortController();

    // Coalesce a burst of events, keeping one snapshot request in flight at a time.
    const fetchBook = (): Promise<void> => {
      requested = true;
      if (fetching) return fetching;
      fetching = (async () => {
        while (requested && !disposed) {
          requested = false;
          try {
            const response = await fetch("/api/book", { signal: abort.signal, cache: "no-store" });
            if (!response.ok) throw await responseError(response);
            const book = decodeBook(await response.json());
            if (disposed) return;
            setReader((current) => receiveBook(current, book));
            setError(null);
            if (!events) {
              events = new EventSource(`/api/events?after=${book.sequence}`);
              events.onopen = () => {
                if (!disposed) {
                  setConnection("live");
                  void fetchBook();
                }
              };
              events.onerror = () => {
                if (!disposed) setConnection("reconnecting");
              };
              events.addEventListener("book_updated", () => {
                void fetchBook();
              });
            }
          } catch (failure) {
            if (!disposed) {
              if (!events) setConnection("offline");
              setError(
                failure instanceof Error ? failure.message : "The book could not be loaded.",
              );
            }
          }
        }
      })().finally(() => {
        fetching = null;
      });
      return fetching;
    };
    refresh.current = fetchBook;
    void fetchBook();
    return () => {
      disposed = true;
      events?.close();
      abort.abort();
    };
  }, [generation]);

  const retry = useCallback(() => {
    setError(null);
    setConnection("connecting");
    setGeneration((value) => value + 1);
  }, []);

  async function post(path: string, body: object): Promise<boolean> {
    if (busy) return false;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw await responseError(response);
      await refresh.current();
      return true;
    } catch (failure) {
      await refresh.current();
      setError(
        failure instanceof Error
          ? failure.message
          : "The request could not be completed. You can retry safely.",
      );
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function start(page: Page) {
    return post("/api/demo/start", { page_id: page.id, expected_revision: page.revision });
  }

  async function decide(page: Page, choice: DecisionChoice, note: string) {
    const signature = JSON.stringify([page.id, page.revision, choice, note]);
    if (decisionRequest.current?.signature !== signature) {
      decisionRequest.current = { signature, requestId: crypto.randomUUID() };
    }
    const success = await post(`/api/pages/${encodeURIComponent(page.id)}/decision`, {
      choice,
      note,
      expected_revision: page.revision,
      request_id: decisionRequest.current.requestId,
    });
    if (success) {
      decisionRequest.current = null;
      setReader((current) => followLatest(current));
    }
    return success;
  }

  return {
    ...reader,
    connection,
    error,
    busy,
    retry,
    start,
    decide,
    select: (id: string) => setReader((current) => selectPage(current, id)),
    follow: () => setReader((current) => followLatest(current)),
  };
}
