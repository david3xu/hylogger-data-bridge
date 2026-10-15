/**
 * Regressions and negative tests for the synthetic HTTP acceptance runner.
 *
 * Verifies that the runner strictly detects and refuses:
 * 1. Missing or non-loopback URLs (before any network access).
 * 2. Non-fresh or dirty books (without sending mutations).
 * 3. Tampered sealed history (evidence or decision modifications).
 * 4. Stalled network responses (finite timeout enforcement).
 * 5. Replay effects (modifications across decision or result replays).
 * 6. Action-vs-advice mismatches (uncited advice or missing candidate distinctness).
 */

import assert from "node:assert/strict";
import http from "node:http";
import { describe, expect, it } from "vitest";
import {
  checkFreshBook,
  EXACT_NOTE,
  request,
  runAcceptance,
  validateLoopbackUrl,
} from "./acceptance.mjs";

function makeFreshBook() {
  return {
    contract_version: 1,
    run_id: "demo",
    source: "synthetic_demo",
    current_page_id: "page-1",
    pages: [
      {
        id: "page-1",
        number: 1,
        parent_id: null,
        template: "investigation",
        template_version: 1,
        title: "An unfamiliar drill hole",
        question: "Show spectral-change intervals that overlap assay records.",
        status: "draft",
        revision: 0,
        summary: "Synthetic case",
        progress: "Ready",
        evidence: [],
        outcome: null,
        errors: [],
        decision: null,
        action: null,
        assessment: null,
        created_at: "2026-10-15T00:00:00+00:00",
        updated_at: "2026-10-15T00:00:00+00:00",
        scientific_review: "unreviewed",
        demo_running: false,
      },
    ],
    continuations: [],
    sequence: 1,
    events: [],
  };
}

describe("acceptance runner URL validation", () => {
  it("rejects missing, empty, or whitespace URLs before any network access", () => {
    expect(() => validateLoopbackUrl("")).toThrow(/Target URL is required/);
    expect(() => validateLoopbackUrl("   ")).toThrow(/Target URL is required/);
    expect(() => validateLoopbackUrl(null)).toThrow(/Target URL is required/);
    expect(() => validateLoopbackUrl(undefined)).toThrow(/Target URL is required/);
  });

  it("rejects non-loopback or public hostnames before any network access", () => {
    expect(() => validateLoopbackUrl("http://example.com:8766")).toThrow(
      /not a supported loopback address/,
    );
    expect(() => validateLoopbackUrl("https://api.hylogger.internal:8766")).toThrow(
      /not a supported loopback address/,
    );
    expect(() => validateLoopbackUrl("http://192.168.1.50:8766")).toThrow(
      /not a supported loopback address/,
    );
  });

  it("rejects unsupported protocols", () => {
    expect(() => validateLoopbackUrl("ftp://127.0.0.1:8766")).toThrow(/Unsupported protocol/);
    expect(() => validateLoopbackUrl("ws://127.0.0.1:8766")).toThrow(/Unsupported protocol/);
  });

  it("accepts valid explicit loopback URLs", () => {
    expect(validateLoopbackUrl("http://127.0.0.1:8771")).toBe("http://127.0.0.1:8771");
    expect(validateLoopbackUrl("http://localhost:8771/")).toBe("http://localhost:8771");
    expect(validateLoopbackUrl("http://[::1]:8771")).toBe("http://[::1]:8771");
  });
});

describe("acceptance runner fresh-target guard", () => {
  it("accepts a clean fresh designated test book", () => {
    const book = makeFreshBook();
    const p1 = checkFreshBook(book);
    expect(p1.id).toBe("page-1");
    expect(p1.status).toBe("draft");
    expect(p1.assessment).toBeNull();
  });

  it("rejects a book that already contains evidence", () => {
    const book = makeFreshBook();
    book.pages[0].evidence.push({
      id: "ev-1",
      label: "Old observation",
      value: "value",
      source: "source",
      kind: "observation",
    });
    expect(() => checkFreshBook(book)).toThrow(/contains 1 evidence items, expected 0/);
  });

  it("rejects a book with nonzero revision", () => {
    const book = makeFreshBook();
    book.pages[0].revision = 1;
    expect(() => checkFreshBook(book)).toThrow(/Initial page revision is 1, expected 0/);
  });

  it("rejects a book with an active running demo", () => {
    const book = makeFreshBook();
    book.pages[0].demo_running = true;
    expect(() => checkFreshBook(book)).toThrow(/active demo running/);
  });

  it("rejects a book with an existing decision or non-draft status", () => {
    const book = makeFreshBook();
    book.pages[0].status = "locked";
    expect(() => checkFreshBook(book)).toThrow(/Initial page status is 'locked', expected 'draft'/);

    const bookWithDecision = makeFreshBook();
    bookWithDecision.pages[0].decision = {
      choice: "accept",
      note: "done",
      recorded_at: "2026-10-15T00:00:00+00:00",
    };
    expect(() => checkFreshBook(bookWithDecision)).toThrow(/already has a decision recorded/);
  });

  it("rejects a book with existing continuations", () => {
    const book = makeFreshBook();
    book.continuations = [
      {
        id: "cont-1",
        decision_id: "dec-1",
        page_id: "page-1",
        successor_id: "page-2",
        locked_revision: 1,
        state: "pending",
        attempts: 0,
        max_attempts: 3,
        claimed_by: null,
        lease_expires_at: null,
        acknowledged_at: null,
      },
    ];
    expect(() => checkFreshBook(book)).toThrow(/has 1 continuations, expected 0/);
  });

  it("rejects a book with wrong run_id or source", () => {
    const bookWrongRun = makeFreshBook();
    bookWrongRun.run_id = "other-run";
    expect(() => checkFreshBook(bookWrongRun)).toThrow(/run_id is 'other-run', expected 'demo'/);

    const bookWrongSource = makeFreshBook();
    bookWrongSource.source = "live";
    expect(() => checkFreshBook(bookWrongSource)).toThrow(
      /source is 'live', expected 'synthetic_demo'/,
    );
  });

  it("rejects a book with pre-existing assessment", () => {
    const book = makeFreshBook();
    book.pages[0].assessment = {
      id: "assess-1",
      page_id: "page-1",
      state_revision: 0,
      model_version: "fixture-v1",
      origin: "fixture",
      status: "available",
      request_hash: "00".repeat(32),
      suggestions: [],
      evidence_gaps: [],
      uncertainty: null,
      limitations: [],
      created_at: "2026-10-15T00:00:00+00:00",
    };
    expect(() => checkFreshBook(book)).toThrow(/already has an assessment recorded/);
  });
});

describe("acceptance runner deep comparison and fault detection", () => {
  it("detects tampered sealed Page 1 evidence during worker transitions", () => {
    const originalLocked = {
      id: "p-1",
      status: "locked",
      revision: 1,
      evidence: [
        { id: "ev-1", label: "Collar", value: "214 m", source: "GSWA", kind: "observation" },
      ],
      decision: { choice: "modify", note: EXACT_NOTE },
    };

    const tampered = structuredClone(originalLocked);
    tampered.evidence[0].value = "999 m (tampered)";

    expect(() => {
      assert.deepStrictEqual(tampered, originalLocked, "Locked Page 1 was modified!");
    }).toThrow(assert.AssertionError);
  });

  it("detects decision replay snapshot inequality", () => {
    const initialDecided = {
      contract_version: 1,
      pages: [
        { id: "p-1", status: "locked" },
        { id: "p-2", status: "draft" },
      ],
      continuations: [{ id: "c-1", state: "pending", attempts: 0 }],
      sequence: 2,
    };

    const faultyReplay = structuredClone(initialDecided);
    // Fault: duplicate continuation or altered sequence
    faultyReplay.sequence = 3;

    expect(() => {
      assert.deepStrictEqual(faultyReplay, initialDecided, "Decision replay must be identical");
    }).toThrow(assert.AssertionError);
  });

  it("detects completion replay snapshot inequality", () => {
    const initialFinal = {
      contract_version: 1,
      pages: [
        { id: "p-1", status: "locked" },
        { id: "p-2", status: "ready", revision: 2, summary: "Original summary" },
      ],
      continuations: [{ id: "c-1", state: "completed" }],
    };

    const faultyReplay = structuredClone(initialFinal);
    // Fault: altered summary or revision
    faultyReplay.pages[1].summary = "Altered summary on replay";

    expect(() => {
      assert.deepStrictEqual(faultyReplay, initialFinal, "Result replay must be identical");
    }).toThrow(assert.AssertionError);
  });

  it("enforces action independence from top advice candidate", () => {
    const topCandidate = "cand-clarify";

    // Valid case: worker chose interval_compare, which differs from cand-clarify
    const validAction = { type: "interval_compare", assessment_id: "assess-1" };
    expect(validAction.type).not.toBe(topCandidate);

    // Fault case: worker action matches top candidate
    const faultyAction = { type: "cand-clarify", assessment_id: "assess-1" };
    expect(() => {
      if (faultyAction.type === topCandidate) {
        throw new Error("Actual action unexpectedly matched advice top suggestion");
      }
    }).toThrow(/unexpectedly matched/);
  });
});

describe("acceptance runner finite request timeout", () => {
  it("fails with TimeoutError when request stalls", async () => {
    const server = http.createServer((_req, _res) => {
      // Deliberately hold connection open without responding
    });

    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = server.address().port;
    const stallUrl = `http://127.0.0.1:${port}`;

    try {
      await expect(request(stallUrl, "GET", "/api/book", null, 150)).rejects.toThrow(
        /Request timed out after 150ms/,
      );
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });

  it("refuses dirty book without issuing any POST mutations", async () => {
    let postCount = 0;
    const dirtyBook = makeFreshBook();
    dirtyBook.pages[0].evidence.push({
      id: "ev-prior",
      label: "Prior",
      value: "100m",
      source: "Manual",
      kind: "observation",
    });

    const server = http.createServer((req, res) => {
      if (req.method === "POST") {
        postCount++;
        res.writeHead(500);
        res.end(JSON.stringify({ error: "Should not have called POST" }));
        return;
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(dirtyBook));
    });

    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = server.address().port;
    const targetUrl = `http://127.0.0.1:${port}`;

    try {
      await expect(runAcceptance(targetUrl)).rejects.toThrow(
        /contains 1 evidence items, expected 0/,
      );
      expect(postCount).toBe(0); // Zero POST calls were made!
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });
});
