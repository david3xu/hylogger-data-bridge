// Perform loopback HTTP requests and subscribe to committed SSE book updates.
import { type Book, type DecisionChoice, decodeBook } from "../state/contracts";

export type ConnectionState = "connecting" | "live" | "reconnecting" | "offline";

export type DecisionSubmissionPayload = {
  choice: DecisionChoice;
  note: string;
  expected_revision: number;
  request_id: string;
};

export async function parseResponseError(response: Response): Promise<Error> {
  let detail = "The local service could not complete this request.";
  try {
    const body = (await response.json()) as Record<string, unknown>;
    if (typeof body.error === "string" && body.error.trim().length > 0) {
      detail = body.error;
    }
  } catch {
    /* Non-JSON error body from proxy or server; fall back to status handling. */
  }
  if (response.status === 409) {
    detail =
      "This page changed. The book has refreshed; review the latest evidence before retrying.";
  }
  return new Error(detail);
}

export async function fetchBookSnapshot(signal?: AbortSignal): Promise<Book> {
  const response = await fetch("/api/book", { signal, cache: "no-store" });
  if (!response.ok) {
    throw await parseResponseError(response);
  }
  return decodeBook(await response.json());
}

export async function postStartDemo(pageId: string, expectedRevision: number): Promise<void> {
  const response = await fetch("/api/demo/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ page_id: pageId, expected_revision: expectedRevision }),
  });
  if (!response.ok) {
    throw await parseResponseError(response);
  }
}

export async function postPageDecision(
  pageId: string,
  payload: DecisionSubmissionPayload,
): Promise<Book> {
  const response = await fetch(`/api/pages/${encodeURIComponent(pageId)}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parseResponseError(response);
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error("The local service returned a malformed decision response.");
  }
  return decodeBook(body);
}

export function isCommittedEventPayload(rawData: string): boolean {
  if (!rawData || !rawData.trim()) return false;
  try {
    const parsed = JSON.parse(rawData) as Record<string, unknown>;
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      typeof parsed.sequence !== "number" ||
      !Number.isSafeInteger(parsed.sequence) ||
      parsed.sequence <= 0 ||
      typeof parsed.type !== "string" ||
      typeof parsed.page_id !== "string"
    ) {
      return false;
    }
    const lowerType = parsed.type.toLowerCase();
    if (lowerType === "keepalive" || lowerType === "heartbeat" || lowerType === "ping") {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

export function subscribeToBookEvents(
  afterSequence: number,
  handlers: {
    onOpen: () => void;
    onError: () => void;
    onCommittedUpdate: (sequence?: number) => void;
  },
): () => void {
  const events = new EventSource(`/api/events?after=${afterSequence}`);
  events.onopen = () => {
    handlers.onOpen();
  };
  events.onerror = () => {
    handlers.onError();
  };
  events.addEventListener("book_updated", (event: MessageEvent<string>) => {
    if (!isCommittedEventPayload(event.data)) {
      return;
    }
    const parsed = JSON.parse(event.data) as { sequence: number };
    handlers.onCommittedUpdate(parsed.sequence);
  });
  return () => {
    events.close();
  };
}
