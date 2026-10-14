// Define and validate the shared snapshot, and preserve reader navigation during live updates.
export type DecisionChoice = "accept" | "modify" | "reject";
export type Evidence = {
  id: string;
  label: string;
  value: string;
  source: string;
  kind: "observation" | "calculation" | "limitation";
};
export type Page = {
  id: string;
  number: number;
  parent_id: string | null;
  template: string;
  template_version: 1;
  title: string;
  question: string;
  status: "draft" | "ready" | "locked";
  revision: number;
  summary: string;
  progress: string;
  evidence: Evidence[];
  decision: { choice: DecisionChoice; note: string; recorded_at: string } | null;
  created_at: string;
  updated_at: string;
  scientific_review: "unreviewed";
  demo_running?: boolean;
};
export type BookEvent = {
  sequence: number;
  type: string;
  page_id: string;
  at: string;
  detail: string;
};
export type Book = {
  run_id: string;
  source: "synthetic_demo";
  current_page_id: string;
  sequence: number;
  pages: Page[];
  events: BookEvent[];
};
export type Reader = { book: Book | null; selectedId: string | null; following: boolean };
export const initialReader: Reader = { book: null, selectedId: null, following: true };

export function receiveBook(reader: Reader, book: Book): Reader {
  if (reader.book && book.sequence < reader.book.sequence) return reader;
  const selectionExists = book.pages.some((page) => page.id === reader.selectedId);
  return {
    ...reader,
    book,
    selectedId: reader.following || !selectionExists ? book.current_page_id : reader.selectedId,
  };
}

export function selectPage(reader: Reader, id: string): Reader {
  if (!reader.book?.pages.some((page) => page.id === id)) return reader;
  return { ...reader, selectedId: id, following: id === reader.book.current_page_id };
}

export function followLatest(reader: Reader): Reader {
  return { ...reader, following: true, selectedId: reader.book?.current_page_id ?? null };
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function strings(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => typeof value[key] === "string");
}
function integer(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function evidence(value: unknown): boolean {
  return (
    object(value) &&
    strings(value, ["id", "label", "value", "source"]) &&
    ["observation", "calculation", "limitation"].includes(String(value.kind))
  );
}
function page(value: unknown): boolean {
  if (
    !object(value) ||
    !strings(value, [
      "id",
      "template",
      "title",
      "question",
      "summary",
      "progress",
      "created_at",
      "updated_at",
    ])
  )
    return false;
  if (
    !integer(value.number) ||
    !integer(value.revision) ||
    value.template_version !== 1 ||
    value.scientific_review !== "unreviewed"
  )
    return false;
  if (value.parent_id !== null && typeof value.parent_id !== "string") return false;
  if (value.demo_running !== undefined && typeof value.demo_running !== "boolean") return false;
  if (!["draft", "ready", "locked"].includes(String(value.status))) return false;
  if (!Array.isArray(value.evidence) || !value.evidence.every(evidence)) return false;
  if (value.decision === null) return value.status !== "locked";
  return (
    value.status === "locked" &&
    object(value.decision) &&
    strings(value.decision, ["note", "recorded_at"]) &&
    ["accept", "modify", "reject"].includes(String(value.decision.choice))
  );
}

export function decodeBook(value: unknown): Book {
  const invalid = new Error("The local service returned an unsupported book snapshot.");
  if (
    !object(value) ||
    !strings(value, ["run_id", "current_page_id"]) ||
    value.source !== "synthetic_demo" ||
    !integer(value.sequence)
  )
    throw invalid;
  if (!Array.isArray(value.pages) || value.pages.length === 0 || !value.pages.every(page))
    throw invalid;
  if (
    !Array.isArray(value.events) ||
    !value.events.every(
      (event: unknown) =>
        object(event) &&
        integer(event.sequence) &&
        strings(event, ["type", "page_id", "at", "detail"]),
    )
  )
    throw invalid;
  const ids = value.pages.map((item: Page) => item.id);
  if (new Set(ids).size !== ids.length || !ids.includes(String(value.current_page_id)))
    throw invalid;
  return value as Book;
}
