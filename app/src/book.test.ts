// Verify live snapshots cannot overwrite newer state or pull a reader out of history.
import { describe, expect, it } from "vitest";
import {
  type Book,
  decodeBook,
  followLatest,
  initialReader,
  type Page,
  receiveBook,
  selectPage,
} from "./book";

function makePage(id: string, number: number): Page {
  return {
    id,
    number,
    parent_id: number > 1 ? "page-1" : null,
    template: "investigation",
    template_version: 1,
    title: "Synthetic investigation",
    question: "Compare synthetic intervals?",
    status: "draft",
    revision: 1,
    summary: "Synthetic example",
    progress: "Waiting",
    evidence: [],
    decision: null,
    created_at: "2026-10-14T00:00:00Z",
    updated_at: "2026-10-14T00:00:00Z",
    scientific_review: "unreviewed",
  };
}

function makeBook(sequence = 1, current = "page-1"): Book {
  return {
    run_id: "demo",
    source: "synthetic_demo",
    sequence,
    current_page_id: current,
    pages:
      current === "page-1"
        ? [makePage("page-1", 1)]
        : [makePage("page-1", 1), makePage("page-2", 2)],
    events: [],
  };
}

describe("live reader", () => {
  it("automatically turns to a new committed page while following", () => {
    const first = receiveBook(initialReader, makeBook());
    const next = receiveBook(first, makeBook(3, "page-2"));
    expect(next.selectedId).toBe("page-2");
    expect(next.following).toBe(true);
  });
  it("preserves reading history while evidence arrives", () => {
    const first = receiveBook(initialReader, makeBook(3, "page-2"));
    const historical = selectPage(first, "page-1");
    const update = receiveBook(historical, makeBook(4, "page-2"));
    expect(update.selectedId).toBe("page-1");
    expect(update.following).toBe(false);
    expect(followLatest(update).selectedId).toBe("page-2");
    expect(followLatest(update).following).toBe(true);
  });
  it("discards a stale snapshot without changing evidence or selection", () => {
    const current = receiveBook(initialReader, makeBook(4, "page-2"));
    expect(receiveBook(current, makeBook(2))).toBe(current);
  });
  it("ignores navigation to a page that does not exist", () => {
    const current = receiveBook(initialReader, makeBook());
    expect(selectPage(current, "missing")).toBe(current);
  });
});

describe("snapshot boundary", () => {
  it("accepts a synthetic snapshot and its genuine locked workflow record", () => {
    const book = makeBook();
    book.pages[0].status = "locked";
    book.pages[0].decision = {
      choice: "modify",
      note: "Compare a smaller interval",
      recorded_at: "2026-10-14T00:00:00Z",
    };
    expect(decodeBook(book)).toEqual(book);
  });
  it.each([null, {}, { ...makeBook(), sequence: -1 }, { ...makeBook(), source: "actual_data" }])(
    "rejects unsupported snapshots",
    (value) => {
      expect(() => decodeBook(value)).toThrow("unsupported book snapshot");
    },
  );
  it("rejects missing current pages and duplicate page identities", () => {
    expect(() => decodeBook({ ...makeBook(), current_page_id: "missing" })).toThrow();
    const book = makeBook();
    book.pages.push(book.pages[0]);
    expect(() => decodeBook(book)).toThrow();
  });
  it("rejects a locked page without a recorded user choice", () => {
    const book = makeBook();
    book.pages[0].status = "locked";
    expect(() => decodeBook(book)).toThrow();
  });
  it("rejects evidence without source or a recognised evidence kind", () => {
    const book = makeBook();
    const malformed = {
      ...book.pages[0],
      evidence: [{ id: "x", label: "Result", value: "3 m", kind: "conclusion" }],
    };
    expect(() => decodeBook({ ...book, pages: [malformed] })).toThrow();
  });
});
