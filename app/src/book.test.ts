// Verify shared v1 schema/fixtures, regressions for all review findings, and hook/browser recovery.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import assessmentFixtures from "../../schemas/fixtures/v1/Assessment.json";
import assessmentRequestFixtures from "../../schemas/fixtures/v1/AssessmentRequest.json";
import bookFixtures from "../../schemas/fixtures/v1/Book.json";
import completionFixtures from "../../schemas/fixtures/v1/Completion.json";
import continuationFixtures from "../../schemas/fixtures/v1/Continuation.json";
import decisionFixtures from "../../schemas/fixtures/v1/Decision.json";
import decisionRequestFixtures from "../../schemas/fixtures/v1/DecisionRequest.json";
import errorFixtures from "../../schemas/fixtures/v1/Error.json";
import evidenceFixtures from "../../schemas/fixtures/v1/Evidence.json";
import handoffFixtures from "../../schemas/fixtures/v1/Handoff.json";
import pageFixtures from "../../schemas/fixtures/v1/Page.json";
import v1Schema from "../../schemas/v1.json";
import { App } from "./App";
import {
  type Assessment,
  type AssessmentRequest,
  type Book,
  type Continuation,
  canDispatchHostHandoff,
  checkAdvice,
  checkBook,
  completeSubmission,
  decodeBook,
  type Evidence,
  failSubmission,
  findContinuationForPage,
  findHostDelivery,
  findParentPage,
  findSuccessorPage,
  followLatest,
  type Handoff,
  initialReader,
  isAssessment,
  isAssessmentDeclined,
  isAssessmentRequest,
  isBookSchemaValid,
  isCompletion,
  isContinuation,
  isContractError,
  isDecision,
  isDecisionConfirmed,
  isDecisionRequest,
  isEvidence,
  isHandoff,
  isHostDeliveryObsolete,
  isPage,
  type Page,
  pauseFollowing,
  prepareSubmission,
  problems,
  receiveBook,
  reconcileHostDeliveries,
  recordHostDelivery,
  resolveAssessment,
  resolveDelivery,
  selectPage,
  setAssessmentDeclined,
  updateDraft,
} from "./book";
import { AssessmentPanel } from "./book/AssessmentPanel";
import { ChapterRail } from "./book/ChapterRail";
import { DecisionForm, SealedDecision } from "./book/DecisionForm";
import { DeliveryStatusBar } from "./book/DeliveryStatusBar";
import { EvidenceList } from "./book/EvidenceList";
import {
  BACKEND_CONTRACT_REQUESTS,
  buildCommittedDecisionNotice,
  deliverAuthoritativeHandoff,
  detectHostCapability,
  formatChatFollowUp,
  type HostDeliveryState,
  type HostTransport,
  isCommittedDecisionNotice,
  notifyCommittedDecision,
  verifyAuthoritativeHandoff,
} from "./host/bridge";
import { PageTemplate } from "./templates/PageTemplate";
import {
  isCommittedEventPayload,
  parseResponseError,
  postPageDecision,
  postStartDemo,
  subscribeToBookEvents,
} from "./transport/api";
import { loadPersistedReader, savePersistedReader, useBook } from "./transport/useBook";

afterEach(() => {
  vi.unstubAllGlobals();
});

type FixtureFile<T = unknown> = {
  valid: Record<string, T>;
  invalid: Record<string, unknown>;
  semantic_invalid?: Record<string, T>;
};

const CANONICAL_FIXTURE_FILES: Record<string, FixtureFile> = {
  Assessment: assessmentFixtures as FixtureFile,
  AssessmentRequest: assessmentRequestFixtures as FixtureFile,
  Book: bookFixtures as FixtureFile,
  Completion: completionFixtures as FixtureFile,
  Continuation: continuationFixtures as FixtureFile,
  Decision: decisionFixtures as FixtureFile,
  DecisionRequest: decisionRequestFixtures as FixtureFile,
  Error: errorFixtures as FixtureFile,
  Evidence: evidenceFixtures as FixtureFile,
  Handoff: handoffFixtures as FixtureFile,
  Page: pageFixtures as FixtureFile,
};

function loadFixtureFile<T = unknown>(name: keyof typeof CANONICAL_FIXTURE_FILES): FixtureFile<T> {
  return CANONICAL_FIXTURE_FILES[name] as FixtureFile<T>;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

const GUARD_BY_DEFINITION: Record<string, (value: unknown) => boolean> = {
  Assessment: isAssessment,
  AssessmentRequest: isAssessmentRequest,
  Book: isBookSchemaValid,
  Completion: isCompletion,
  Continuation: isContinuation,
  Decision: isDecision,
  DecisionRequest: isDecisionRequest,
  Error: isContractError,
  Evidence: isEvidence,
  Handoff: isHandoff,
  Page: isPage,
};

describe("canonical shared schema and fixtures (schemas/v1.json & schemas/fixtures/v1/*.json)", () => {
  it("loads all 11 canonical fixture files and verifies every valid and invalid case against schemas/v1.json", () => {
    const names = Object.keys(CANONICAL_FIXTURE_FILES).sort();
    expect(names.length).toBe(11);

    const defs = (v1Schema as { $defs: Record<string, unknown> }).$defs;
    for (const name of names) {
      expect(name in defs).toBe(true);
      const fixture = loadFixtureFile(name);
      expect(Object.keys(fixture.valid).length).toBeGreaterThan(0);
      expect(Object.keys(fixture.invalid).length).toBeGreaterThan(0);

      const guard = GUARD_BY_DEFINITION[name];
      expect(typeof guard).toBe("function");

      for (const [caseName, value] of Object.entries(fixture.valid)) {
        expect(problems(name, value), `${name}.valid.${caseName}`).toEqual([]);
        expect(guard(value), `${name}.valid.${caseName} guard`).toBe(true);
      }

      for (const [caseName, value] of Object.entries(fixture.invalid)) {
        expect(problems(name, value).length, `${name}.invalid.${caseName}`).toBeGreaterThan(0);
        expect(guard(value), `${name}.invalid.${caseName} guard`).toBe(false);
      }
    }
  });

  it("enforces all semantic Book rules against schemas/fixtures/v1/Book.json", () => {
    const fixtures = loadFixtureFile<Book>("Book");

    for (const [caseName, book] of Object.entries(fixtures.valid)) {
      expect(() => checkBook(book), `Book.valid.${caseName}`).not.toThrow();
      expect(decodeBook(book).run_id).toBe(book.run_id);
    }

    const semanticInvalid = fixtures.semantic_invalid ?? {};
    expect(Object.keys(semanticInvalid).length).toBeGreaterThanOrEqual(13);
    for (const [caseName, book] of Object.entries(semanticInvalid)) {
      expect(problems("Book", book), `Book.semantic_invalid.${caseName} schema`).toEqual([]);
      expect(() => checkBook(book), `Book.semantic_invalid.${caseName} checkBook`).toThrow();
      expect(() => decodeBook(book), `Book.semantic_invalid.${caseName} decodeBook`).toThrow();
    }
  });

  it("enforces all semantic Assessment rules against schemas/fixtures/v1/Assessment.json and AssessmentRequest.json", () => {
    const request = loadFixtureFile<AssessmentRequest>("AssessmentRequest").valid.basic;
    const adviceFixtures = loadFixtureFile<Assessment>("Assessment");
    const expectedHash = adviceFixtures.valid["fixture-available"].request_hash;

    for (const [caseName, advice] of Object.entries(adviceFixtures.valid)) {
      expect(
        () => checkAdvice(request, advice, expectedHash),
        `Assessment.valid.${caseName}`,
      ).not.toThrow();
    }

    const semanticInvalid = adviceFixtures.semantic_invalid ?? {};
    expect(Object.keys(semanticInvalid).length).toBeGreaterThanOrEqual(7);
    for (const [caseName, advice] of Object.entries(semanticInvalid)) {
      expect(
        problems("Assessment", advice),
        `Assessment.semantic_invalid.${caseName} schema`,
      ).toEqual([]);
      expect(
        () => checkAdvice(request, advice, expectedHash),
        `Assessment.semantic_invalid.${caseName} checkAdvice`,
      ).toThrow();
    }
  });

  it("validates every canonical Page fixture and renders ready-advised where action differs from top suggestion", () => {
    const pages = loadFixtureFile<Page>("Page").valid;
    const readyAdvised = clone(pages["ready-advised"]);
    const resolved = resolveAssessment(readyAdvised, false);
    expect(resolved.status).toBe("fixture");
    expect(resolved.actualAction).toContain("qa_check");
    expect(resolved.actualAction).toContain("consulted assess-1");
    expect(resolved.assessment.suggestions[0].candidate_id).toBe("cand-overlap");
  });

  it("maps every canonical Continuation.json valid state into backend-confirmed delivery states", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const conts = loadFixtureFile<Continuation>("Continuation").valid;
    const readyPageFixture = clone(loadFixtureFile<Page>("Page").valid["ready-advised"]);

    const pendingBook: Book = { ...decidedBook, continuations: [clone(conts.pending)] };
    expect(resolveDelivery(pendingBook, pendingBook.pages[0]).state).toBe("pending_delivery");
    expect(resolveDelivery(pendingBook, pendingBook.pages[1]).state).toBe("pending_delivery");

    const retryPendingBook: Book = {
      ...decidedBook,
      continuations: [clone(conts["retry-pending"])],
    };
    const retryRes = resolveDelivery(retryPendingBook, retryPendingBook.pages[1]);
    expect(retryRes.state).toBe("pending_delivery");
    expect(retryRes.summary).toContain("attempt 1/3");
    expect(retryRes.detail).toContain("delivery_failed");

    const runningBook: Book = { ...decidedBook, continuations: [clone(conts.running)] };
    const runningRes = resolveDelivery(runningBook, runningBook.pages[1]);
    expect(runningRes.state).toBe("working");
    expect(runningRes.summary).toContain("worker-1");

    const ackedRunningBook: Book = {
      ...decidedBook,
      continuations: [
        {
          ...clone(conts.running),
          acknowledged_at: "2026-10-14T09:11:15+00:00",
        },
      ],
    };
    expect(resolveDelivery(ackedRunningBook, ackedRunningBook.pages[1]).state).toBe("accepted");

    const completedBook: Book = {
      ...decidedBook,
      pages: [
        decidedBook.pages[0],
        { ...readyPageFixture, id: "page-2", number: 2, parent_id: "page-1" },
      ],
      continuations: [clone(conts.completed)],
    };
    expect(resolveDelivery(completedBook, completedBook.pages[1]).state).toBe("ready");

    const failedBook: Book = { ...decidedBook, continuations: [clone(conts.failed)] };
    const failedRes = resolveDelivery(failedBook, failedBook.pages[1]);
    expect(failedRes.state).toBe("failed");
    expect(failedRes.summary).toContain("3/3 attempts");
  });
});

describe("finding #1: no browser-constructed claim attempts, leases, or fallback IDs; distinct notice vs Handoff", () => {
  it("keeps automatic host dispatch unavailable by default and documents the backend contract requirement", () => {
    expect(BACKEND_CONTRACT_REQUESTS.authoritativeHandoffOperation.status).toBe(
      "pending_backend_agreement",
    );
    const capability = detectHostCapability();
    expect(capability.mode).toBe("standalone");
    expect(capability.available).toBe(false);
    expect(capability.automaticDispatchAvailable).toBe(false);
    expect(capability.detail).toContain("use explicit chat follow-up");
  });

  it("keeps a CommittedDecisionNotice strictly distinct from a leased worker Handoff and never fabricates fallback IDs", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const canonicalHandoff = clone(loadFixtureFile<Handoff>("Handoff").valid.committed);
    const lockedPage = decidedBook.pages[0];

    const notice = buildCommittedDecisionNotice(decidedBook, lockedPage);
    expect(notice).not.toBeNull();
    if (!notice) return;

    expect(isCommittedDecisionNotice(notice)).toBe(true);
    expect(isHandoff(notice)).toBe(false);
    expect(isCommittedDecisionNotice(canonicalHandoff)).toBe(false);
    expect(isHandoff(canonicalHandoff)).toBe(true);

    expect("attempt" in notice).toBe(false);
    expect("claimed_by" in notice).toBe(false);
    expect("lease_expires_at" in notice).toBe(false);
    expect(notice.decision_id).toBe("dec-1");
    expect(notice.continuation_id).toBe("cont-1");

    // Pre-v1 snapshot without continuation or decision.id must return null IDs rather than inventing cont-* or dec-*
    const legacyBook: Book = {
      run_id: "demo",
      source: "synthetic_demo",
      current_page_id: "page-2",
      sequence: 2,
      pages: [
        {
          ...lockedPage,
          decision: {
            choice: "modify",
            note: "Look at the assay interval first.",
            recorded_at: "2026-10-14T09:10:00+00:00",
          },
        },
        decidedBook.pages[1],
      ],
      continuations: [],
      events: decidedBook.events,
    };
    const legacyNotice = buildCommittedDecisionNotice(legacyBook, legacyBook.pages[0]);
    expect(legacyNotice).not.toBeNull();
    expect(legacyNotice?.decision_id).toBeNull();
    expect(legacyNotice?.continuation_id).toBeNull();

    // Unknown actor decisions are never notified or handed off
    const unknownBook = clone(loadFixtureFile<Book>("Book").valid["legacy-unknown-actor"]);
    expect(buildCommittedDecisionNotice(unknownBook, unknownBook.pages[0])).toBeNull();
    expect(
      verifyAuthoritativeHandoff(unknownBook, unknownBook.pages[0], canonicalHandoff),
    ).toBeNull();
  });

  it("renders explicit chat follow-up on committed human decisions while automatic dispatch is unavailable", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const deliveryOnLocked = resolveDelivery(decidedBook, decidedBook.pages[0]);
    expect(deliveryOnLocked.state).toBe("pending_delivery");
    expect(deliveryOnLocked.chatFollowUp).toContain(
      'Continue HyLogger investigation (run=demo page=page-1@r7 successor=page-2 decision=dec-1 continuation=cont-1): choice=modify — "Look at the assay interval first."',
    );

    const html = renderToStaticMarkup(
      createElement(DeliveryStatusBar, { delivery: deliveryOnLocked }),
    );
    expect(html).toContain("Copy chat follow-up");
    expect(html).toContain("continuation=cont-1");
  });
});

describe("finding #2: reconcile local transport records against authoritative continuation progress", () => {
  it("clears obsolete failure/retry state and prevents duplicate dispatch once continuation completes or successor is ready", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const canonicalHandoff = clone(loadFixtureFile<Handoff>("Handoff").valid.committed);
    const continuations = loadFixtureFile<Continuation>("Continuation").valid;
    const readyPageFixture = clone(loadFixtureFile<Page>("Page").valid["ready-advised"]);

    let reader = receiveBook(initialReader, decidedBook);
    const failedDelivery: HostDeliveryState = {
      pageId: "page-1",
      successorId: "page-2",
      continuationId: "cont-1",
      decisionId: "dec-1",
      handoff: canonicalHandoff,
      status: "failed",
      error: "Host bridge timed out on attempt 1",
      attempts: 1,
    };
    reader = recordHostDelivery(reader, failedDelivery);

    // While continuation is still pending on backend and page-2 is an empty draft, retry is permitted
    const pendingDelivery = resolveDelivery(
      reader.book,
      decidedBook.pages[1],
      undefined,
      findHostDelivery(reader, decidedBook.pages[1]),
    );
    expect(pendingDelivery.state).toBe("failed");
    expect(pendingDelivery.retryableHostDelivery).toBe(true);
    expect(canDispatchHostHandoff(decidedBook, "page-1", failedDelivery)).toBe(true);

    // Backend progresses continuation to running under a worker lease
    const runningBook: Book = {
      ...decidedBook,
      sequence: 3,
      continuations: [clone(continuations.running)],
    };
    const afterRunning = receiveBook(reader, runningBook);
    expect(afterRunning.hostDeliveries["page-1"]).toBeUndefined();
    const runningResolved = resolveDelivery(
      afterRunning.book,
      runningBook.pages[1],
      undefined,
      findHostDelivery(afterRunning, runningBook.pages[1]),
    );
    expect(runningResolved.state).toBe("working");
    expect(runningResolved.retryableHostDelivery).toBe(false);

    // Backend completes continuation and marks page-2 ready
    const completedBook: Book = {
      ...decidedBook,
      sequence: 4,
      pages: [
        decidedBook.pages[0],
        {
          ...readyPageFixture,
          id: "page-2",
          number: 2,
          parent_id: "page-1",
        },
      ],
      continuations: [clone(continuations.completed)],
    };
    expect(isHostDeliveryObsolete(completedBook, failedDelivery)).toBe(true);
    expect(reconcileHostDeliveries(completedBook, { "page-1": failedDelivery })).toEqual({});
    expect(canDispatchHostHandoff(completedBook, "page-1", failedDelivery)).toBe(false);

    const afterCompleted = receiveBook(reader, completedBook);
    expect(afterCompleted.hostDeliveries["page-1"]).toBeUndefined();

    // Even if a stale failedDelivery object is passed directly to resolveDelivery, completed/ready backend state wins
    const resolvedOnReady = resolveDelivery(
      completedBook,
      completedBook.pages[1],
      undefined,
      failedDelivery,
    );
    expect(resolvedOnReady.state).toBe("ready");
    expect(resolvedOnReady.label).toBe("Ready");
    expect(resolvedOnReady.retryableHostDelivery).toBe(false);
    expect(resolvedOnReady.chatFollowUp).toBeUndefined();

    const resolvedOnParent = resolveDelivery(
      completedBook,
      completedBook.pages[0],
      undefined,
      failedDelivery,
    );
    expect(resolvedOnParent.state).toBe("ready");
    expect(resolvedOnParent.retryableHostDelivery).toBe(false);
  });

  it("prevents duplicate dispatch when continuation is already accepted or terminal failed", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const canonicalHandoff = clone(loadFixtureFile<Handoff>("Handoff").valid.committed);
    const continuations = loadFixtureFile<Continuation>("Continuation").valid;

    const acceptedDelivery: HostDeliveryState = {
      pageId: "page-1",
      successorId: "page-2",
      continuationId: "cont-1",
      decisionId: "dec-1",
      handoff: canonicalHandoff,
      status: "accepted",
      error: null,
      attempts: 1,
    };
    expect(canDispatchHostHandoff(decidedBook, "page-1", acceptedDelivery)).toBe(false);

    const failedBook: Book = {
      ...decidedBook,
      continuations: [clone(continuations.failed)],
    };
    expect(canDispatchHostHandoff(failedBook, "page-1")).toBe(false);
    expect(findContinuationForPage(failedBook, failedBook.pages[1])?.state).toBe("failed");
  });
});

describe("finding #3: coherent confirmed submission and successor navigation (including after Pause following & SSE-before-POST)", () => {
  it("transitions to the successor page when submitting after Pause following", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const readyPage1: Page = {
      ...decidedBook.pages[0],
      status: "ready",
      decision: null,
    };
    const initialBook: Book = {
      ...decidedBook,
      current_page_id: "page-1",
      sequence: 1,
      pages: [readyPage1],
      continuations: [],
      events: [decidedBook.events[0]],
    };

    // User pauses following while on page-1
    let reader = pauseFollowing(receiveBook(initialReader, initialBook));
    expect(reader.following).toBe(false);
    expect(reader.selectedId).toBe("page-1");

    // User prepares submission
    const prepared = prepareSubmission(
      reader,
      readyPage1,
      "modify",
      "Look at the assay interval first.",
      () => "req-1",
    );
    reader = prepared.reader;

    // Case A: POST response arrives and runs receiveBook + completeSubmission
    const afterPost = completeSubmission(
      receiveBook(reader, decidedBook),
      "page-1",
      prepared.draft,
    );
    expect(afterPost.selectedId).toBe("page-2");
    expect(afterPost.following).toBe(true);
    expect(afterPost.drafts["page-1"]).toBeUndefined();

    // Case B: SSE confirmation arrives BEFORE POST response while following is paused
    const afterSseFirst = receiveBook(reader, decidedBook);
    expect(afterSseFirst.selectedId).toBe("page-2");
    expect(afterSseFirst.following).toBe(true);
    expect(afterSseFirst.drafts["page-1"]).toBeUndefined();

    // Subsequent POST resolution is a clean, idempotent transition that keeps page-2 selected
    const afterLatePost = completeSubmission(
      receiveBook(afterSseFirst, decidedBook),
      "page-1",
      prepared.draft,
    );
    expect(afterLatePost.selectedId).toBe("page-2");
    expect(afterLatePost.following).toBe(true);
    expect(afterLatePost.drafts["page-1"]).toBeUndefined();
  });

  it("preserves paused history reading when unrelated background SSE updates arrive without a confirmed submission", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    let reader = receiveBook(initialReader, decidedBook);
    reader = selectPage(reader, "page-1");
    expect(reader.following).toBe(false);
    expect(reader.selectedId).toBe("page-1");

    const updatedPage2Book: Book = {
      ...decidedBook,
      sequence: 3,
      pages: [
        decidedBook.pages[0],
        {
          ...decidedBook.pages[1],
          revision: 1,
          demo_running: true,
        },
      ],
    };
    reader = receiveBook(reader, updatedPage2Book);
    expect(reader.selectedId).toBe("page-1");
    expect(reader.following).toBe(false);

    reader = followLatest(reader);
    expect(reader.selectedId).toBe("page-2");
    expect(reader.following).toBe(true);
  });
});

describe("finding #4: accept canonical source='live' and confine synthetic labels to synthetic content", () => {
  it("validates source='live' books and renders live provenance without synthetic labels", () => {
    const baseBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const actualEvidence: Evidence = {
      ...clone(loadFixtureFile<Evidence>("Evidence").valid["complete-observation"]),
      id: "live-qa",
      label: "Package depth alignment",
      value: "Verified 0.5 m tray sampling linkage across 180–260 m",
      source: "GSWA HyLogger package MSDP01",
      origin: "actual",
      state: "complete",
    };
    const liveAssessment: Assessment = {
      ...clone(loadFixtureFile<Assessment>("Assessment").valid["fixture-available"]),
      id: "assess-live-1",
      page_id: "page-2",
      state_revision: 1,
      model_version: "hylogger-selector-v1",
      origin: "model",
      suggestions: [
        {
          candidate_id: "cand-overlap",
          rank: 1,
          rationale: "Prioritise interval comparison where actual QA coverage is complete.",
          evidence_ids: [actualEvidence.id],
        },
      ],
      evidence_gaps: [],
      uncertainty: "Moderate uncertainty across unsampled contact.",
      limitations: ["Advisory ranking only; does not certify resource intervals."],
    };

    const existingDecision = baseBook.pages[0].decision;
    expect(existingDecision).not.toBeNull();
    if (!existingDecision) return;

    const liveBook: Book = {
      ...baseBook,
      source: "live",
      pages: [
        {
          ...baseBook.pages[0],
          evidence: [actualEvidence],
          decision: {
            ...existingDecision,
            evidence_ids: [actualEvidence.id],
          },
        },
        {
          ...baseBook.pages[1],
          status: "ready",
          revision: 1,
          outcome: "complete",
          evidence: [actualEvidence],
          action: {
            type: "qa_check",
            assessment_id: "assess-live-1",
            actor: { kind: "agent", name: "worker-1" },
            recorded_at: "2026-10-14T09:15:00+00:00",
          },
          assessment: liveAssessment,
        },
      ],
    };

    expect(() => checkBook(liveBook)).not.toThrow();
    expect(decodeBook(liveBook).source).toBe("live");

    const railHtml = renderToStaticMarkup(
      createElement(ChapterRail, {
        book: liveBook,
        selectedPageId: "page-2",
        hostCapability: detectHostCapability(),
        onSelectPage: () => {},
      }),
    );
    expect(railHtml).toContain("Live investigation");
    expect(railHtml).not.toContain("Synthetic demonstration");
    expect(railHtml).not.toContain("No real drill-hole data");

    const evidenceHtml = renderToStaticMarkup(
      createElement(EvidenceList, {
        evidence: liveBook.pages[1].evidence,
        bookSource: liveBook.source,
      }),
    );
    expect(evidenceHtml).toContain("Provenance: actual");
    expect(evidenceHtml).toContain("live book provenance");
    expect(evidenceHtml).not.toContain("Synthetic interval view");
    expect(evidenceHtml).not.toContain("Provenance: synthetic");

    const resolvedAssess = resolveAssessment(liveBook.pages[1], false, liveBook.source);
    expect(resolvedAssess.status).toBe("model");
    expect(resolvedAssess.badgeLabel).toBe("Local decision model (origin=model)");
    const assessHtml = renderToStaticMarkup(
      createElement(AssessmentPanel, {
        resolved: resolvedAssess,
        pageRevision: liveBook.pages[1].revision,
        onToggleDecline: () => {},
      }),
    );
    expect(assessHtml).toContain("Local decision model (origin=model)");
    expect(assessHtml).not.toContain("Fixture advice");
    expect(assessHtml).not.toContain("synthetic");
  });

  it("keeps local advice decline as a viewing preference and never writes it into SealedDecision history", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    let reader = receiveBook(initialReader, decidedBook);
    reader = setAssessmentDeclined(reader, "page-1", true);
    expect(isAssessmentDeclined(reader, "page-1")).toBe(true);

    const sealedHtml = renderToStaticMarkup(
      createElement(SealedDecision, {
        page: decidedBook.pages[0],
        successorPage: decidedBook.pages[1],
        onSelectPage: () => {},
      }),
    );
    expect(sealedHtml).not.toContain("declined");
    expect(sealedHtml).toContain("Look at the assay interval first.");
  });
});

describe("hook, transport, and browser session recovery coverage", () => {
  it("recovers submitting drafts and delivering host records from sessionStorage as retryable failed states", () => {
    const canonicalHandoff = clone(loadFixtureFile<Handoff>("Handoff").valid.committed);
    const storage = new Map<string, string>();
    vi.stubGlobal("window", {
      sessionStorage: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, val: string) => {
          storage.set(key, val);
        },
      },
    });

    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const readyPage: Page = {
      ...decidedBook.pages[0],
      status: "ready",
      decision: null,
    };
    const prepared = prepareSubmission(
      initialReader,
      readyPage,
      "modify",
      "Look at the assay interval first.",
      () => "req-1",
    );
    const withDelivering = recordHostDelivery(prepared.reader, {
      pageId: "page-1",
      successorId: "page-2",
      continuationId: "cont-1",
      decisionId: "dec-1",
      handoff: canonicalHandoff,
      status: "delivering",
      error: null,
      attempts: 1,
    });

    savePersistedReader(withDelivering);
    const restored = loadPersistedReader();
    expect(restored.drafts["page-1"]?.status).toBe("failed");
    expect(restored.drafts["page-1"]?.requestId).toBe("req-1");
    expect(restored.hostDeliveries["page-1"]?.status).toBe("failed");

    // Once the backend snapshot confirms both the decision and completed continuation, receiveBook reconciles both
    const completedCont = clone(loadFixtureFile<Continuation>("Continuation").valid.completed);
    const completedBook: Book = {
      ...decidedBook,
      continuations: [completedCont],
    };
    const reconciled = receiveBook(restored, completedBook);
    expect(reconciled.drafts["page-1"]).toBeUndefined();
    expect(reconciled.hostDeliveries["page-1"]).toBeUndefined();
    expect(reconciled.selectedId).toBe("page-2");
  });

  it("rejects malformed HTTP 200 decision responses and preserves unconfirmed drafts", async () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const readyPage: Page = {
      ...decidedBook.pages[0],
      status: "ready",
      decision: null,
    };
    const unconfirmedBook: Book = {
      ...decidedBook,
      current_page_id: "page-1",
      sequence: 1,
      pages: [readyPage],
      continuations: [],
      events: [decidedBook.events[0]],
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ malformed: true }),
      }),
    );

    await expect(
      postPageDecision("page-1", {
        choice: "modify",
        note: "Look at the assay interval first.",
        expected_revision: 7,
        request_id: "req-1",
      }),
    ).rejects.toThrow("unsupported book snapshot");

    const reader = receiveBook(initialReader, unconfirmedBook);
    const prepared = prepareSubmission(
      reader,
      readyPage,
      "modify",
      "Look at the assay interval first.",
      () => "req-1",
    );
    const afterUnconfirmed = completeSubmission(
      receiveBook(prepared.reader, unconfirmedBook),
      "page-1",
      prepared.draft,
    );
    expect(afterUnconfirmed.drafts["page-1"]?.status).toBe("failed");
    expect(afterUnconfirmed.drafts["page-1"]?.requestId).toBe("req-1");
    expect(afterUnconfirmed.selectedId).toBe("page-1");
  });

  it("verifies authoritative backend handoff before host delivery and refuses mismatched or completed handoffs", async () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const canonicalHandoff = clone(loadFixtureFile<Handoff>("Handoff").valid.committed);
    const lockedPage = decidedBook.pages[0];

    expect(verifyAuthoritativeHandoff(decidedBook, lockedPage, canonicalHandoff)).toEqual(
      canonicalHandoff,
    );

    // Mismatched continuation_id is rejected
    expect(
      verifyAuthoritativeHandoff(decidedBook, lockedPage, {
        ...canonicalHandoff,
        continuation_id: "cont-other",
      }),
    ).toBeNull();

    // Verified transport delivers authoritative handoff and records receipt
    const transport: HostTransport = {
      contractVersion: 1,
      hostName: "codex-desktop-test",
      fetchAuthoritativeHandoff: async () => canonicalHandoff,
      deliverHandoff: async (h) => ({ accepted: h.attempt === 1, detail: "Accepted attempt 1" }),
      notifyDecisionCommitted: async () => ({ accepted: true, detail: "Notified" }),
    };
    const outcome = await deliverAuthoritativeHandoff(canonicalHandoff, transport);
    expect(outcome.accepted).toBe(true);

    const notice = buildCommittedDecisionNotice(decidedBook, lockedPage);
    expect(notice).not.toBeNull();
    if (!notice) return;
    const noticeOutcome = await notifyCommittedDecision(notice, transport);
    expect(noticeOutcome.accepted).toBe(true);
  });

  it("ignores keepalive/heartbeat SSE payloads and only triggers on committed events", () => {
    expect(isCommittedEventPayload("")).toBe(false);
    expect(isCommittedEventPayload(": keepalive")).toBe(false);
    expect(
      isCommittedEventPayload(
        JSON.stringify({ sequence: 1, type: "keepalive", page_id: "page-1" }),
      ),
    ).toBe(false);
    expect(
      isCommittedEventPayload(
        JSON.stringify({ sequence: 1, type: "heartbeat", page_id: "page-1" }),
      ),
    ).toBe(false);
    expect(
      isCommittedEventPayload(
        JSON.stringify({ sequence: 2, type: "decision_recorded", page_id: "page-1" }),
      ),
    ).toBe(true);
  });

  it("exercises useBook hook end-to-end: pause following, SSE confirmation before POST response, and host recovery reconciliation", async () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const canonicalHandoff = clone(loadFixtureFile<Handoff>("Handoff").valid.committed);
    const completedCont = clone(loadFixtureFile<Continuation>("Continuation").valid.completed);
    const readyPage1: Page = {
      ...decidedBook.pages[0],
      status: "ready",
      decision: null,
    };
    const initialBook: Book = {
      ...decidedBook,
      current_page_id: "page-1",
      sequence: 1,
      pages: [readyPage1],
      continuations: [],
      events: [decidedBook.events[0]],
    };

    const harness: {
      currentServerBook: Book;
      resolveDecisionPost: ((book: Book) => void) | null;
      sseEmitUpdate: ((seq?: number) => void) | null;
      viewer: ReturnType<typeof useBook> | null;
    } = {
      currentServerBook: initialBook,
      resolveDecisionPost: null,
      sseEmitUpdate: null,
      viewer: null,
    };

    class MockEventSource {
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      private listeners = new Map<string, Array<(ev: MessageEvent<string>) => void>>();
      constructor(_url: string) {
        harness.sseEmitUpdate = (seq = 2) => {
          const cbs = this.listeners.get("book_updated") ?? [];
          for (const cb of cbs) {
            cb({
              data: JSON.stringify({
                sequence: seq,
                type: "decision_recorded",
                page_id: "page-1",
              }),
            } as MessageEvent<string>);
          }
        };
      }
      addEventListener(type: string, cb: (ev: MessageEvent<string>) => void) {
        const list = this.listeners.get(type) ?? [];
        list.push(cb);
        this.listeners.set(type, list);
      }
      close() {}
    }

    const storage = new Map<string, string>();
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal("window", {
      scrollTo: () => {},
      sessionStorage: {
        getItem: (k: string) => storage.get(k) ?? null,
        setItem: (k: string, v: string) => {
          storage.set(k, v);
        },
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string, init?: RequestInit) => {
        if (input === "/api/book") {
          return {
            ok: true,
            status: 200,
            json: async () => harness.currentServerBook,
          };
        }
        if (input === "/api/pages/page-1/decision") {
          const parsedBody =
            typeof init?.body === "string"
              ? (JSON.parse(init.body) as { request_id: string })
              : { request_id: "req-1" };
          const baseDecision = decidedBook.pages[0].decision;
          if (baseDecision) {
            decidedBook.pages[0] = {
              ...decidedBook.pages[0],
              decision: {
                ...baseDecision,
                request_id: parsedBody.request_id,
              },
            };
          }
          return new Promise((resolvePost) => {
            harness.resolveDecisionPost = (book: Book) => {
              resolvePost({
                ok: true,
                status: 200,
                json: async () => book,
              });
            };
          });
        }
        throw new Error(`Unexpected URL ${input}`);
      }),
    );

    let deliverShouldAccept = false;
    let deliverCount = 0;
    const mockTransport: HostTransport = {
      contractVersion: 1,
      hostName: "codex-host",
      fetchAuthoritativeHandoff: async () => canonicalHandoff,
      deliverHandoff: async () => {
        deliverCount += 1;
        return {
          accepted: deliverShouldAccept,
          detail: deliverShouldAccept ? "Accepted" : "Host rejected attempt",
        };
      },
    };

    function HookProbe() {
      harness.viewer = useBook(mockTransport);
      return createElement(App);
    }

    renderToStaticMarkup(createElement(HookProbe));
    const viewer = harness.viewer;
    expect(viewer).not.toBeNull();
    if (!viewer) return;

    const disconnect = viewer.connect();
    await new Promise((r) => setTimeout(r, 15));
    expect(viewer.getState().book?.current_page_id).toBe("page-1");
    expect(viewer.getState().selectedId).toBe("page-1");
    expect(viewer.getState().following).toBe(true);

    // 1. User clicks Pause following while on ready page-1
    viewer.pause();
    expect(viewer.getState().following).toBe(false);

    // 2. User submits decision on page-1; POST is held in flight
    const decidePromise = viewer.decide(readyPage1, "modify", "Look at the assay interval first.");
    expect(viewer.getState().drafts["page-1"]?.status).toBe("submitting");

    // 3. SSE confirmation arrives BEFORE POST response resolves!
    harness.currentServerBook = decidedBook;
    harness.sseEmitUpdate?.(2);
    await new Promise((r) => setTimeout(r, 15));
    expect(viewer.getState().selectedId).toBe("page-2");
    expect(viewer.getState().following).toBe(true);
    expect(viewer.getState().drafts["page-1"]).toBeUndefined();

    // 4. Now the POST response resolves; decide completes cleanly and triggers authoritative host delivery (which fails on attempt 1)
    harness.resolveDecisionPost?.(decidedBook);
    const decideResult = await decidePromise;
    expect(decideResult).toBe(true);
    expect(viewer.getState().selectedId).toBe("page-2");
    expect(viewer.getState().following).toBe(true);
    expect(viewer.getState().hostDeliveries["page-1"]?.status).toBe("failed");
    expect(deliverCount).toBe(1);

    // 5. Backend completes continuation before user retries host delivery; SSE update clears obsolete failure and prevents duplicate dispatch
    harness.currentServerBook = {
      ...decidedBook,
      sequence: 3,
      continuations: [completedCont],
    };
    harness.sseEmitUpdate?.(3);
    await new Promise((r) => setTimeout(r, 15));
    expect(viewer.getState().hostDeliveries["page-1"]).toBeUndefined();

    deliverShouldAccept = true;
    const retryResult = await viewer.retryHostDelivery("page-1");
    expect(retryResult).toBe(false);
    expect(deliverCount).toBe(1);

    disconnect();

    expect(typeof postStartDemo).toBe("function");
    expect(typeof parseResponseError).toBe("function");
    expect(typeof subscribeToBookEvents).toBe("function");
    expect(typeof PageTemplate).toBe("function");
    expect(typeof DecisionForm).toBe("function");
    expect(typeof SealedDecision).toBe("function");
    expect(typeof findParentPage).toBe("function");
    expect(typeof findSuccessorPage).toBe("function");
    expect(typeof selectPage).toBe("function");
    expect(typeof followLatest).toBe("function");
    expect(typeof updateDraft).toBe("function");
    expect(typeof failSubmission).toBe("function");
    expect(typeof setAssessmentDeclined).toBe("function");
    expect(typeof isAssessmentDeclined).toBe("function");
    expect(typeof isDecisionConfirmed).toBe("function");
    expect(typeof formatChatFollowUp).toBe("function");
  });
});
