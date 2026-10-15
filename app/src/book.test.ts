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
  BUILTIN_SYNTHETIC_SOURCE,
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
import { copyTextToClipboard, DeliveryStatusBar } from "./book/DeliveryStatusBar";
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
  parseChatFollowUp,
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
    expect(resolved.assessment?.suggestions[0].candidate_id).toBe("cand-overlap");
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

describe("PR #5 audit finding #1: assessment:null shows 'No assessment recorded.' without generated IDs/hashes/claims", () => {
  it("renders 'No assessment recorded.' for assessment:null and never invents IDs, hashes, timestamps, or model-installation claims", () => {
    const pages = loadFixtureFile<Page>("Page").valid;
    for (const [name, page] of Object.entries(pages)) {
      if (page.assessment !== null) continue;
      const resolved = resolveAssessment(page, false, "synthetic_demo");
      expect(resolved.status, `${name} status`).toBe("none");
      expect(resolved.badgeLabel, `${name} badgeLabel`).toBe("No assessment recorded");
      expect(resolved.assessment, `${name} assessment`).toBeNull();
      expect(resolved.isStale, `${name} isStale`).toBe(false);
      expect(resolved.referencedEvidenceIds, `${name} referencedEvidenceIds`).toEqual([]);

      const html = renderToStaticMarkup(
        createElement(AssessmentPanel, {
          resolved,
          pageRevision: page.revision,
          onToggleDecline: () => {},
        }),
      );
      expect(html).toContain("No assessment recorded.");
      expect(html).not.toContain("Request hash:");
      expect(html).not.toContain("ID:");
      expect(html).not.toContain("Model:");
      expect(html).not.toContain("No local model is installed");
      expect(html).not.toContain("fixture-v1");
    }
  });

  it("preserves genuine backend unavailable, fixture, model, and stale Assessment records verbatim", () => {
    const pages = loadFixtureFile<Page>("Page").valid;
    const assessments = loadFixtureFile<Assessment>("Assessment").valid;
    const readyAdvised = clone(pages["ready-advised"]);

    // 1. Genuine fixture-available assessment
    const fixtureResolved = resolveAssessment(readyAdvised, false);
    expect(fixtureResolved.status).toBe("fixture");
    expect(fixtureResolved.assessment).toEqual(assessments["fixture-available"]);

    // 2. Genuine backend unavailable assessment
    const unavailPage: Page = {
      ...readyAdvised,
      assessment: clone(assessments.unavailable),
    };
    const unavailResolved = resolveAssessment(unavailPage, false);
    expect(unavailResolved.status).toBe("unavailable");
    expect(unavailResolved.assessment).toEqual(assessments.unavailable);
    const unavailHtml = renderToStaticMarkup(
      createElement(AssessmentPanel, {
        resolved: unavailResolved,
        pageRevision: unavailPage.revision,
        onToggleDecline: () => {},
      }),
    );
    expect(unavailHtml).toContain("assess-2");
    expect(unavailHtml).toContain(
      "No local model is installed; manual or deterministic work remains possible.",
    );

    // 3. Genuine stale assessment (state_revision < page.revision)
    const stalePage: Page = {
      ...readyAdvised,
      revision: 9,
      assessment: clone(assessments["fixture-available"]),
    };
    const staleResolved = resolveAssessment(stalePage, false);
    expect(staleResolved.status).toBe("stale");
    expect(staleResolved.isStale).toBe(true);
    expect(staleResolved.assessment?.id).toBe("assess-1");
  });
});

describe("PR #5 audit finding #2: conservative legacy provenance decoding", () => {
  it("preserves validated explicit legacy values, uses synthetic only for the exact built-in fixture source, and defaults others to unspecified/unknown", () => {
    const legacyRaw = {
      run_id: "demo",
      source: "synthetic_demo",
      current_page_id: "page-2",
      sequence: 2,
      pages: [
        {
          id: "page-1",
          number: 1,
          parent_id: null,
          template: "investigation",
          template_version: 1,
          title: "An unfamiliar drill hole",
          question: "Show spectral-change intervals that overlap assay records.",
          status: "locked",
          revision: 3,
          summary: "Summary",
          progress: "Ready",
          evidence: [
            {
              id: "ev-builtin",
              label: "Quality check",
              value: "Passed",
              source: BUILTIN_SYNTHETIC_SOURCE,
              kind: "observation",
            },
            {
              id: "ev-custom",
              label: "External note",
              value: "Unverified source",
              source: "Custom legacy script v0",
              kind: "observation",
            },
            {
              id: "ev-explicit-actual",
              label: "Measured collar",
              value: "214 m",
              source: "GSWA collar table",
              kind: "observation",
              origin: "actual",
              state: "partial",
            },
          ],
          decision: {
            choice: "modify",
            note: "Inspect interval.",
            recorded_at: "2026-10-14T09:10:00+00:00",
          },
          created_at: "2026-10-14T09:00:00+00:00",
          updated_at: "2026-10-14T09:10:00+00:00",
          scientific_review: "unreviewed",
        },
        {
          id: "page-2",
          number: 2,
          parent_id: "page-1",
          template: "candidate_evidence",
          template_version: 1,
          title: "Follow-up",
          question: "Show spectral-change intervals that overlap assay records.",
          status: "draft",
          revision: 0,
          summary: "Follow-up",
          progress: "Waiting",
          evidence: [],
          decision: null,
          created_at: "2026-10-14T09:10:00+00:00",
          updated_at: "2026-10-14T09:10:00+00:00",
          scientific_review: "unreviewed",
        },
      ],
      events: [],
    };

    const decoded = decodeBook(legacyRaw);
    const [evBuiltin, evCustom, evExplicit] = decoded.pages[0].evidence;
    expect(evBuiltin.origin).toBe("synthetic");
    expect(evBuiltin.state).toBe("complete");
    expect(evCustom.origin).toBe("unspecified");
    expect(evCustom.state).toBe("complete");
    expect(evExplicit.origin).toBe("actual");
    expect(evExplicit.state).toBe("partial");

    // Legacy decision without explicit actor defaults conservatively to unknown and is never notified
    expect(decoded.pages[0].decision?.actor).toEqual({ kind: "unknown" });
    expect(buildCommittedDecisionNotice(decoded, decoded.pages[0])).toBeNull();

    // Explicit valid human actor on a legacy record is preserved
    const legacyWithHumanActor = clone(legacyRaw);
    (legacyWithHumanActor.pages[0].decision as Record<string, unknown>).actor = {
      kind: "human",
      name: "reviewer-1",
    };
    const decodedHuman = decodeBook(legacyWithHumanActor);
    expect(decodedHuman.pages[0].decision?.actor).toEqual({
      kind: "human",
      name: "reviewer-1",
    });

    // Invalid explicit origin, state, or actor in legacy snapshot is rejected
    const badOrigin = clone(legacyRaw);
    (badOrigin.pages[0].evidence[0] as Record<string, unknown>).origin = "invented";
    expect(() => decodeBook(badOrigin)).toThrow();

    const badState = clone(legacyRaw);
    (badState.pages[0].evidence[0] as Record<string, unknown>).state = "pending";
    expect(() => decodeBook(badState)).toThrow();

    const badActor = clone(legacyRaw);
    (badActor.pages[0].decision as Record<string, unknown>).actor = { kind: "agent" };
    expect(() => decodeBook(badActor)).toThrow();
  });
});

describe("PR #5 audit finding #3: clipboard copy verification, error reporting, and selectable fallback", () => {
  it("reports clipboard success only after writeText resolves and handles absent or denied clipboard with error + selectable fallback", async () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const delivery = resolveDelivery(decidedBook, decidedBook.pages[0]);
    expect(delivery.chatFollowUp).toBeDefined();
    const targetText = delivery.chatFollowUp ?? "";

    // 1. Absent clipboard API returns ok=false with error message
    const absentResult = await copyTextToClipboard(targetText, undefined);
    expect(absentResult.ok).toBe(false);
    expect(absentResult.error).toContain("Clipboard access is unavailable");

    // 2. Denied clipboard API (writeText rejects) returns ok=false with error reason
    const deniedResult = await copyTextToClipboard(targetText, {
      clipboard: {
        writeText: async () => {
          throw new Error("Write permission denied");
        },
      },
    });
    expect(deniedResult.ok).toBe(false);
    expect(deniedResult.error).toContain("Write permission denied");

    // 3. Successful clipboard API resolves ok=true only after copying exact text
    const copiedTexts: string[] = [];
    const okResult = await copyTextToClipboard(targetText, {
      clipboard: {
        writeText: async (val: string) => {
          copiedTexts.push(val);
        },
      },
    });
    expect(okResult.ok).toBe(true);
    expect(okResult.error).toBeNull();
    expect(copiedTexts).toEqual([targetText]);

    // 4. DeliveryStatusBar renders error alert and selectable fallback input when copy fails
    const failedHtml = renderToStaticMarkup(
      createElement(DeliveryStatusBar, {
        delivery,
        initialCopyError: absentResult.error,
      }),
    );
    expect(failedHtml).toContain('role="alert"');
    expect(failedHtml).toContain("Clipboard access is unavailable");
    expect(failedHtml).toContain("Retry copy chat follow-up");
    expect(failedHtml).toContain('class="chat-followup-fallback"');
    expect(failedHtml).toContain('aria-label="Selectable chat follow-up text"');
    expect(failedHtml).not.toContain("Copied chat follow-up");
  });
});

describe("PR #5 audit finding #4: exact note preservation and round-trip recovery in follow-up text", () => {
  it("preserves whitespace, quotes, newlines, backslashes, and Unicode in follow-up text and recovers them losslessly", () => {
    const decidedBook = clone(loadFixtureFile<Book>("Book").valid["decided-with-successor"]);
    const basePage = decidedBook.pages[0];
    const baseDecision = basePage.decision;
    expect(baseDecision).not.toBeNull();
    if (!baseDecision) return;

    const trickyNotes = [
      "",
      "   ",
      "\t  leading and trailing whitespace \n ",
      "Reviewer said: \"Check 214–220 m\" & 're-log' path C:\\cores\\hole-1",
      "Line 1: 214–220 m\nLine 2:\tcheck assay overlap\r\nLine 3: parentheses (decision=dec-99)",
      "Unicode provenance: 214–220 m · δ¹⁸O ± 0.2‰ · 碳酸盐岩 🪨",
    ];

    for (const note of trickyNotes) {
      const pageWithNote: Page = {
        ...basePage,
        decision: {
          ...baseDecision,
          note,
        },
      };
      const bookWithNote: Book = {
        ...decidedBook,
        pages: [pageWithNote, decidedBook.pages[1]],
      };
      const notice = buildCommittedDecisionNotice(bookWithNote, pageWithNote);
      expect(notice).not.toBeNull();
      if (!notice) continue;

      expect(notice.note).toBe(note);
      const formatted = formatChatFollowUp(notice);
      const parsed = parseChatFollowUp(formatted);
      expect(parsed, `round-trip for ${JSON.stringify(note)}`).not.toBeNull();
      expect(parsed?.note).toBe(note);
      expect(parsed?.run_id).toBe(notice.run_id);
      expect(parsed?.page_id).toBe(notice.page_id);
      expect(parsed?.locked_revision).toBe(notice.locked_revision);
      expect(parsed?.successor_id).toBe(notice.successor_id);
      expect(parsed?.decision_id).toBe(notice.decision_id);
      expect(parsed?.continuation_id).toBe(notice.continuation_id);
      expect(parsed?.choice).toBe(notice.choice);
    }
  });
});

describe("prior audit regressions (#1-#4 from earlier review)", () => {
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

    // Unknown actor decisions are never notified or handed off
    const unknownBook = clone(loadFixtureFile<Book>("Book").valid["legacy-unknown-actor"]);
    expect(buildCommittedDecisionNotice(unknownBook, unknownBook.pages[0])).toBeNull();
    expect(
      verifyAuthoritativeHandoff(unknownBook, unknownBook.pages[0], canonicalHandoff),
    ).toBeNull();
  });

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

    const pendingDelivery = resolveDelivery(
      reader.book,
      decidedBook.pages[1],
      undefined,
      findHostDelivery(reader, decidedBook.pages[1]),
    );
    expect(pendingDelivery.state).toBe("failed");
    expect(pendingDelivery.retryableHostDelivery).toBe(true);
    expect(canDispatchHostHandoff(decidedBook, "page-1", failedDelivery)).toBe(true);

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

    const resolvedOnReady = resolveDelivery(
      completedBook,
      completedBook.pages[1],
      undefined,
      failedDelivery,
    );
    expect(resolvedOnReady.state).toBe("ready");
    expect(resolvedOnReady.retryableHostDelivery).toBe(false);
    expect(findContinuationForPage(completedBook, completedBook.pages[1])?.state).toBe("completed");
  });

  it("transitions to the successor page when submitting after Pause following (including SSE confirmation before POST)", () => {
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

    let reader = pauseFollowing(receiveBook(initialReader, initialBook));
    expect(reader.following).toBe(false);

    const prepared = prepareSubmission(
      reader,
      readyPage1,
      "modify",
      "Look at the assay interval first.",
      () => "req-1",
    );
    reader = prepared.reader;

    const afterSseFirst = receiveBook(reader, decidedBook);
    expect(afterSseFirst.selectedId).toBe("page-2");
    expect(afterSseFirst.following).toBe(true);
    expect(afterSseFirst.drafts["page-1"]).toBeUndefined();

    const afterLatePost = completeSubmission(
      receiveBook(afterSseFirst, decidedBook),
      "page-1",
      prepared.draft,
    );
    expect(afterLatePost.selectedId).toBe("page-2");
    expect(afterLatePost.following).toBe(true);
    expect(afterLatePost.drafts["page-1"]).toBeUndefined();
  });

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

    const evidenceHtml = renderToStaticMarkup(
      createElement(EvidenceList, {
        evidence: liveBook.pages[1].evidence,
        bookSource: liveBook.source,
      }),
    );
    expect(evidenceHtml).toContain("Provenance: actual");
    expect(evidenceHtml).not.toContain("Provenance: synthetic");

    const resolvedAssess = resolveAssessment(liveBook.pages[1], false, liveBook.source);
    expect(resolvedAssess.status).toBe("model");
    const assessHtml = renderToStaticMarkup(
      createElement(AssessmentPanel, {
        resolved: resolvedAssess,
        pageRevision: liveBook.pages[1].revision,
        onToggleDecline: () => {},
      }),
    );
    expect(assessHtml).toContain("Local decision model (origin=model)");
    expect(assessHtml).not.toContain("Fixture advice");
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

    expect(
      verifyAuthoritativeHandoff(decidedBook, lockedPage, {
        ...canonicalHandoff,
        continuation_id: "cont-other",
      }),
    ).toBeNull();

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

    viewer.pause();
    expect(viewer.getState().following).toBe(false);

    const draftNote = '  Automated test: compare "SWIR"\nKeep exact whitespace — Δ  ';
    viewer.updateDecisionDraft(readyPage1, "modify", draftNote);
    expect(loadPersistedReader().drafts[readyPage1.id]?.note).toBe(draftNote);
    expect(viewer.getState().book?.pages[0].decision).toBeNull();
    expect(vi.mocked(fetch).mock.calls.every((call) => call[1]?.method !== "POST")).toBe(true);
    const decidePromise = viewer.decide(readyPage1, "modify", "Look at the assay interval first.");
    expect(viewer.getState().drafts["page-1"]?.status).toBe("submitting");

    harness.currentServerBook = decidedBook;
    harness.sseEmitUpdate?.(2);
    await new Promise((r) => setTimeout(r, 15));
    expect(viewer.getState().selectedId).toBe("page-2");
    expect(viewer.getState().following).toBe(true);
    expect(viewer.getState().drafts["page-1"]).toBeUndefined();

    harness.resolveDecisionPost?.(decidedBook);
    const decideResult = await decidePromise;
    expect(decideResult).toBe(true);
    expect(viewer.getState().selectedId).toBe("page-2");
    expect(viewer.getState().following).toBe(true);
    expect(viewer.getState().hostDeliveries["page-1"]?.status).toBe("failed");
    expect(deliverCount).toBe(1);

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
