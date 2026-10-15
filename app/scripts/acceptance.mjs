#!/usr/bin/env node
/**
 * Synthetic HTTP acceptance runner for HyLogger Data Bridge.
 *
 * Verifies backend lifecycle contracts, atomic decisions, attempt fencing,
 * bounded retries, fixture advice, and locked history preservation over HTTP.
 *
 * Usage:
 *   node app/scripts/acceptance.mjs <loopbackURL>
 *   node app/scripts/acceptance.mjs http://127.0.0.1:8771
 */

import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

export const EXACT_NOTE =
  "   Exact human note with padding: check 214–220 m · δ¹⁸O ± 0.2‰ · \"quotes\" & 'single' · \t tab \n newline! 🪨   ";

export function log(phase, message) {
  console.log(`[HTTP ACCEPTANCE] [${phase}] ${message}`);
}

export function fail(phase, message) {
  const err = new Error(`[HTTP ACCEPTANCE] [FAIL] [${phase}] ${message}`);
  err.phase = phase;
  throw err;
}

export function validateLoopbackUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== "string" || !rawUrl.trim()) {
    fail(
      "URL_REQUIRED",
      "Target URL is required. Provide an explicit loopback URL (e.g. http://127.0.0.1:8771).",
    );
  }
  let parsed;
  try {
    parsed = new URL(rawUrl.trim());
  } catch (err) {
    fail(
      "URL_INVALID",
      `Invalid URL '${rawUrl}': ${err.message}. Provide a valid loopback URL (e.g. http://127.0.0.1:8771).`,
    );
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    fail("URL_PROTOCOL", `Unsupported protocol '${parsed.protocol}'. Expected http: or https:.`);
  }
  const host = parsed.hostname;
  const isLoopback =
    host === "127.0.0.1" || host === "localhost" || host === "[::1]" || host === "::1";
  if (!isLoopback) {
    fail(
      "URL_NON_LOOPBACK",
      `Target '${rawUrl}' is not a supported loopback address (127.0.0.1, localhost, [::1]). ` +
        "Acceptance checks must target a dedicated local test instance.",
    );
  }
  return parsed.origin;
}

export function checkFreshBook(book) {
  if (!book || typeof book !== "object") {
    fail("PRECONDITION", "Target returned an invalid book payload.");
  }
  if (book.run_id !== "demo") {
    fail("PRECONDITION", `Target book run_id is '${book.run_id}', expected 'demo'.`);
  }
  if (book.source !== "synthetic_demo") {
    fail("PRECONDITION", `Target book source is '${book.source}', expected 'synthetic_demo'.`);
  }
  if (book.contract_version !== 1) {
    fail("PRECONDITION", `Target book contract_version is ${book.contract_version}, expected 1.`);
  }
  if (!Array.isArray(book.pages) || book.pages.length !== 1) {
    fail(
      "PRECONDITION",
      `Target book must have exactly 1 initial page, found ${book.pages?.length ?? 0}.`,
    );
  }
  const p1 = book.pages[0];
  if (p1.number !== 1) {
    fail("PRECONDITION", `Initial page number is ${p1.number}, expected 1.`);
  }
  if (p1.parent_id !== null) {
    fail("PRECONDITION", `Initial page parent_id is ${p1.parent_id}, expected null.`);
  }
  if (p1.status !== "draft") {
    fail("PRECONDITION", `Initial page status is '${p1.status}', expected 'draft'.`);
  }
  if (p1.revision !== 0) {
    fail("PRECONDITION", `Initial page revision is ${p1.revision}, expected 0.`);
  }
  if (!Array.isArray(p1.evidence) || p1.evidence.length !== 0) {
    fail(
      "PRECONDITION",
      `Initial page contains ${p1.evidence?.length} evidence items, expected 0.`,
    );
  }
  if (!Array.isArray(p1.errors) || p1.errors.length !== 0) {
    fail("PRECONDITION", `Initial page contains ${p1.errors?.length} errors, expected 0.`);
  }
  if (p1.decision !== null) {
    fail("PRECONDITION", "Initial page already has a decision recorded.");
  }
  if (p1.action !== null) {
    fail("PRECONDITION", "Initial page already has an action recorded.");
  }
  if (p1.assessment !== null) {
    fail("PRECONDITION", "Initial page already has an assessment recorded, expected null.");
  }
  if (p1.demo_running) {
    fail("PRECONDITION", "Initial page has an active demo running.");
  }
  if (book.current_page_id !== p1.id) {
    fail(
      "PRECONDITION",
      `Book current_page_id '${book.current_page_id}' does not match initial page ID '${p1.id}'.`,
    );
  }
  if (Array.isArray(book.continuations) && book.continuations.length > 0) {
    fail("PRECONDITION", `Target book has ${book.continuations.length} continuations, expected 0.`);
  }
  return p1;
}

export function checkLockedPageImmutability(
  currentPage0,
  originalLockedPage,
  context = "transition",
) {
  if (!currentPage0 || !originalLockedPage) {
    fail("IMMUTABILITY", `Missing page for locked history check during ${context}.`);
  }
  try {
    assert.deepStrictEqual(currentPage0, originalLockedPage);
  } catch (err) {
    fail("IMMUTABILITY", `Locked Page 1 was modified during ${context}! Details: ${err.message}`);
  }
}

export function checkReplaySnapshotEquality(
  replaySnapshot,
  expectedSnapshot,
  operation = "Replay",
) {
  if (!replaySnapshot || !expectedSnapshot) {
    fail("IDEMPOTENCE", `Missing snapshot for replay equality check (${operation}).`);
  }
  try {
    assert.deepStrictEqual(replaySnapshot, expectedSnapshot);
  } catch (err) {
    fail(
      "IDEMPOTENCE",
      `${operation} snapshot inequality: replay response must be completely equal to initial snapshot (pages, revision, continuations, events). Details: ${err.message}`,
    );
  }
}

export function checkActionIndependence(executedAction, advice, candidates) {
  if (!executedAction || typeof executedAction !== "object") {
    fail("ACTION_INDEPENDENCE", "Missing or invalid executed action payload.");
  }
  if (!executedAction.type) {
    fail("ACTION_INDEPENDENCE", "Executed action is missing 'type'.");
  }
  if (!advice || typeof advice !== "object") {
    fail("ACTION_INDEPENDENCE", "Missing or invalid assessment advice.");
  }
  if (!executedAction.assessment_id) {
    fail("ACTION_INDEPENDENCE", "Executed action does not cite an assessment_id.");
  }
  if (executedAction.assessment_id !== advice.id) {
    fail(
      "ACTION_INDEPENDENCE",
      `Recorded action assessment_id '${executedAction.assessment_id}' does not match advice ID '${advice.id}'.`,
    );
  }
  if (!Array.isArray(advice.suggestions) || advice.suggestions.length === 0) {
    fail("ACTION_INDEPENDENCE", "Advice contains no suggestions.");
  }
  const topSuggestion = advice.suggestions[0];
  const topCandidateId = topSuggestion.candidate_id;
  if (!topCandidateId) {
    fail("ACTION_INDEPENDENCE", "Top suggestion has no candidate_id.");
  }

  // Treat candidate IDs as opaque and resolve via candidate list
  if (!Array.isArray(candidates) || candidates.length === 0) {
    fail("ACTION_INDEPENDENCE", "Candidate list must be a non-empty array.");
  }
  const candidateMap = new Map();
  for (const c of candidates) {
    if (c && typeof c === "object" && c.id && c.action_type) {
      candidateMap.set(c.id, c.action_type);
    }
  }

  const topActionType = candidateMap.get(topCandidateId);
  if (!topActionType) {
    fail(
      "ACTION_INDEPENDENCE",
      `Unknown top candidate ID '${topCandidateId}' returned by advice (not found in candidate list).`,
    );
  }

  if (executedAction.type === topActionType) {
    fail(
      "ACTION_INDEPENDENCE",
      `Actual action '${executedAction.type}' unexpectedly matched advice top suggestion '${topActionType}' (candidate ID '${topCandidateId}'). Expected worker to choose an independent action.`,
    );
  }

  return {
    executedActionType: executedAction.type,
    topCandidateId,
    topActionType,
  };
}

export async function request(baseURL, method, path, body = null, timeoutMs = 4000) {
  const url = `${baseURL}${path}`;
  const options = {
    method,
    headers: {
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(timeoutMs),
  };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, options);
  } catch (err) {
    if (err.name === "TimeoutError") {
      fail("TIMEOUT", `Request timed out after ${timeoutMs}ms: ${method} ${path}`);
    }
    fail(
      "NETWORK",
      `Could not connect to ${url}: ${err.message}. Ensure the book server is running.`,
    );
  }
  let data;
  try {
    data = await res.json();
  } catch (err) {
    fail("RESPONSE", `Invalid JSON from ${method} ${path} (${res.status}): ${err.message}`);
  }
  return { status: res.status, ok: res.ok, data };
}

export async function runAcceptance(targetUrl, options = {}) {
  const requestTimeoutMs = options.requestTimeoutMs ?? 4000;
  const pollBudgetMs = options.pollBudgetMs ?? 10000;

  const baseURL = validateLoopbackUrl(targetUrl);
  log("START", `Connecting to target loopback service at ${baseURL}`);

  // Step 1: Verify service is reachable and acting on a fresh designated test book
  // (Fails before any mutation POST if book is non-fresh)
  const init = await request(baseURL, "GET", "/api/book", null, requestTimeoutMs);
  if (!init.ok || init.status !== 200) {
    fail("INIT", `GET /api/book returned HTTP ${init.status}: ${JSON.stringify(init.data)}`);
  }
  const page1 = checkFreshBook(init.data);
  const page1Id = page1.id;
  const page1InitialRev = page1.revision;

  log("CHECK", "Fresh book confirmed: single draft page 1 with assessment: null.");

  // Step 2: Trigger staged synthetic runner and readiness-poll until page 1 is ready
  log("POLL", `Starting synthetic demo on draft page ${page1Id} (rev ${page1InitialRev})`);
  const startRes = await request(
    baseURL,
    "POST",
    "/api/demo/start",
    {
      page_id: page1Id,
      expected_revision: page1InitialRev,
    },
    requestTimeoutMs,
  );
  if (startRes.status !== 202 || startRes.data.started !== true) {
    fail("DEMO_START", `POST /api/demo/start failed: ${JSON.stringify(startRes.data)}`);
  }

  // Readiness poll loop with bounded overall timeout
  let readyBook = null;
  const pollStart = Date.now();
  while (Date.now() - pollStart < pollBudgetMs) {
    await new Promise((resolve) => setTimeout(resolve, 150));
    const poll = await request(baseURL, "GET", "/api/book", null, requestTimeoutMs);
    if (poll.ok && poll.data.pages?.[0]?.status === "ready") {
      readyBook = poll.data;
      break;
    }
  }
  if (!readyBook) {
    fail("TIMEOUT", `Page 1 did not reach ready state within ${pollBudgetMs}ms budget.`);
  }
  const readyPage1 = readyBook.pages[0];
  if (readyPage1.evidence.length !== 5) {
    fail("EVIDENCE", `Expected 5 synthetic evidence items, found ${readyPage1.evidence.length}.`);
  }
  const readyRevision = readyPage1.revision;
  log(
    "POLL",
    `Page 1 ready with ${readyPage1.evidence.length} evidence items (rev ${readyRevision}).`,
  );

  // Step 3: Commit exact human decision and verify atomic lock + successor creation
  const decisionReqId = `req-accept-${Date.now()}`;
  log("DECISION", `Committing decision: choice=modify, requestId=${decisionReqId}`);
  const decideRes = await request(
    baseURL,
    "POST",
    `/api/pages/${page1Id}/decision`,
    {
      choice: "modify",
      note: EXACT_NOTE,
      expected_revision: readyRevision,
      request_id: decisionReqId,
    },
    requestTimeoutMs,
  );
  if (!decideRes.ok || decideRes.status !== 200) {
    fail(
      "DECISION",
      `Decision commit failed (${decideRes.status}): ${JSON.stringify(decideRes.data)}`,
    );
  }
  const decidedBook = decideRes.data;
  if (decidedBook.pages.length !== 2) {
    fail("SUCCESSOR", `Expected exactly 2 pages after decision, found ${decidedBook.pages.length}`);
  }
  const lockedP1 = decidedBook.pages.find((p) => p.id === page1Id);
  const p1Decision = lockedP1?.decision;
  if (!lockedP1 || lockedP1.status !== "locked" || !p1Decision) {
    fail("LOCK", "Page 1 was not locked or lacks decision record.");
  }
  if (p1Decision.choice !== "modify" || p1Decision.note !== EXACT_NOTE) {
    fail(
      "EXACT_NOTE",
      "Committed decision note mismatch. Expected exact note with padding/Unicode/tabs/newlines.",
    );
  }

  // Retain the complete locked Page 1 snapshot object for deep-comparison verification
  const originalLockedPage = structuredClone(lockedP1);

  const successorId = p1Decision.successor_id;
  const successorPage = decidedBook.pages.find((p) => p.id === successorId);
  if (!successorPage || successorPage.status !== "draft" || successorPage.parent_id !== page1Id) {
    fail("SUCCESSOR", "Successor page not correctly linked as child draft.");
  }

  const continuations = decidedBook.continuations || [];
  const cont = continuations.find((c) => c.page_id === page1Id);
  if (!cont || cont.state !== "pending" || cont.attempts !== 0 || cont.max_attempts !== 3) {
    fail(
      "CONTINUATION",
      `Continuation not queued as pending with 0/3 attempts: ${JSON.stringify(cont)}`,
    );
  }
  const continuationId = cont.id;
  log(
    "DECISION",
    `Decision sealed. Page 1 locked, successor ${successorId} draft, continuation ${continuationId} pending.`,
  );

  // Step 4: Verify decision idempotence with complete snapshot equality
  log("IDEMPOTENCE", "Replaying identical decision request ID to verify snapshot equality");
  const replayDecideRes = await request(
    baseURL,
    "POST",
    `/api/pages/${page1Id}/decision`,
    {
      choice: "modify",
      note: EXACT_NOTE,
      expected_revision: readyRevision,
      request_id: decisionReqId,
    },
    requestTimeoutMs,
  );
  if (!replayDecideRes.ok || replayDecideRes.status !== 200) {
    fail("IDEMPOTENCE", "Decision replay request failed.");
  }
  checkReplaySnapshotEquality(replayDecideRes.data, decidedBook, "Decision replay");
  log(
    "IDEMPOTENCE",
    "Decision replay verified completely identical across all pages, continuations, and events.",
  );

  // Step 5: Worker claim, acknowledgement, and bounded failure/retry
  log("WORKER", "Worker claiming delivery attempt 1...");
  const claim1 = await request(
    baseURL,
    "POST",
    "/api/work/claim_delivery",
    {
      worker: "test-eval-worker",
      seconds: 30,
    },
    requestTimeoutMs,
  );
  if (!claim1.ok || !claim1.data.handoff) {
    fail("CLAIM", `Claim delivery failed: ${JSON.stringify(claim1.data)}`);
  }
  const handoff1 = claim1.data.handoff;
  if (
    handoff1.continuation_id !== continuationId ||
    handoff1.attempt !== 1 ||
    handoff1.note !== EXACT_NOTE ||
    handoff1.choice !== "modify"
  ) {
    fail("HANDOFF", `Handoff payload mismatch: ${JSON.stringify(handoff1)}`);
  }
  log("WORKER", "Attempt 1 claimed. Exact note with padding and choice preserved in handoff.");

  // Acknowledge attempt 1
  const ack1 = await request(
    baseURL,
    "POST",
    "/api/work/acknowledge_delivery",
    {
      continuation_id: continuationId,
      attempt: 1,
      seconds: 30,
    },
    requestTimeoutMs,
  );
  const ackCont1 = ack1.data.continuations?.find((c) => c.id === continuationId);
  if (!ack1.ok || !ackCont1?.acknowledged_at) {
    fail("ACK", `Acknowledge attempt 1 failed: ${JSON.stringify(ack1.data)}`);
  }
  log("WORKER", `Attempt 1 acknowledged at ${ackCont1.acknowledged_at}.`);

  // Simulate bounded worker failure using canonical Error contract
  log("FAILURE", "Failing attempt 1 with canonical Error payload...");
  const fail1 = await request(
    baseURL,
    "POST",
    "/api/work/fail_delivery",
    {
      continuation_id: continuationId,
      attempt: 1,
      error: {
        error: "Simulated worker transient failure",
        code: "delivery_failed",
        retryable: true,
      },
    },
    requestTimeoutMs,
  );
  if (!fail1.ok) {
    fail("FAIL_DELIVERY", `fail_delivery returned ${fail1.status}: ${JSON.stringify(fail1.data)}`);
  }
  const failCont1 = fail1.data.continuations?.find((c) => c.id === continuationId);
  if (
    !failCont1 ||
    failCont1.state !== "pending" ||
    failCont1.attempts !== 1 ||
    failCont1.max_attempts !== 3 ||
    failCont1.last_error?.code !== "delivery_failed"
  ) {
    fail(
      "RETRY_STATE",
      `Failed continuation not returned to pending: ${JSON.stringify(failCont1)}`,
    );
  }
  if (fail1.data.pages.length !== 2) {
    fail("SAFETY", "Failed delivery attempt produced duplicate successor pages!");
  }
  // Deep-compare sealed Page 1 after failed delivery
  checkLockedPageImmutability(fail1.data.pages[0], originalLockedPage, "worker failure transition");

  // Verify attempt log
  const attemptsRes = await request(
    baseURL,
    "POST",
    "/api/work/read_attempts",
    {
      continuation_id: continuationId,
    },
    requestTimeoutMs,
  );
  const attempts = attemptsRes.data.attempts || [];
  if (attempts.length !== 1 || attempts[0].attempt !== 1 || attempts[0].ended !== "failed") {
    fail("READ_ATTEMPTS", `Attempts record mismatch: ${JSON.stringify(attempts)}`);
  }
  log(
    "FAILURE",
    "Attempt 1 recorded as failed; delivery returned to pending (1/3 attempts) without duplicate pages.",
  );

  // Step 6: Claim attempt 2, add incremental evidence, request assessment, and complete
  log("WORKER", "Worker claiming attempt 2...");
  const claim2 = await request(
    baseURL,
    "POST",
    "/api/work/claim_delivery",
    {
      worker: "test-eval-worker",
      seconds: 60,
    },
    requestTimeoutMs,
  );
  const handoff2 = claim2.data?.handoff;
  if (!claim2.ok || handoff2?.attempt !== 2) {
    fail("CLAIM_2", `Claim attempt 2 failed: ${JSON.stringify(claim2.data)}`);
  }
  // Derive claim token directly from returned matching handoff
  const claimToken = { continuation_id: handoff2.continuation_id, attempt: handoff2.attempt };

  const ack2 = await request(
    baseURL,
    "POST",
    "/api/work/acknowledge_delivery",
    {
      continuation_id: continuationId,
      attempt: 2,
      seconds: 60,
    },
    requestTimeoutMs,
  );
  const ackCont2 = ack2.data.continuations?.find((c) => c.id === continuationId);
  if (!ack2.ok || !ackCont2?.acknowledged_at) {
    fail("ACK_2", `Acknowledge attempt 2 failed: ${JSON.stringify(ack2.data)}`);
  }
  log("WORKER", `Attempt 2 acknowledged at ${ackCont2.acknowledged_at}.`);

  // Submit incremental evidence under claim
  const evRes = await request(
    baseURL,
    "POST",
    "/api/work/submit_evidence",
    {
      page_id: successorId,
      expected_revision: successorPage.revision,
      evidence: {
        id: "ev-acceptance-check",
        label: "Acceptance verification assay check",
        value: "Synthetic: 214–220 m interval evaluated against criteria",
        source: "Synthetic acceptance test runner",
        kind: "observation",
        origin: "synthetic",
        state: "complete",
      },
      claim: claimToken,
    },
    requestTimeoutMs,
  );
  if (!evRes.ok) {
    fail("SUBMIT_EVIDENCE", `submit_evidence failed: ${JSON.stringify(evRes.data)}`);
  }
  // Deep-compare sealed Page 1 after incremental evidence
  checkLockedPageImmutability(evRes.data.pages[0], originalLockedPage, "submit_evidence");
  const p2AfterEv = evRes.data.pages.find((p) => p.id === successorId);
  const p2RevAfterEv = p2AfterEv.revision;
  log(
    "EVIDENCE",
    `Incremental evidence submitted to successor page (rev incremented to ${p2RevAfterEv}).`,
  );

  // Request real backend fixture assessment with explicit candidates
  log("ASSESSMENT", "Requesting assessment from backend (FixtureProvider)...");
  const explicitCandidates = [
    {
      id: "cand-opt-clarify",
      action_type: "clarify",
      arguments: {},
    },
    {
      id: "cand-opt-compare",
      action_type: "interval_compare",
      arguments: {},
    },
    {
      id: "cand-opt-qa",
      action_type: "qa_check",
      arguments: {},
    },
  ];
  const assessRes = await request(
    baseURL,
    "POST",
    "/api/work/request_assessment",
    {
      page_id: successorId,
      expected_revision: p2RevAfterEv,
      candidates: explicitCandidates,
    },
    requestTimeoutMs,
  );
  if (!assessRes.ok) {
    fail("ASSESSMENT", `request_assessment failed: ${JSON.stringify(assessRes.data)}`);
  }
  // Deep-compare sealed Page 1 after request_assessment
  checkLockedPageImmutability(assessRes.data.pages[0], originalLockedPage, "request_assessment");

  const p2Advised = assessRes.data.pages.find((p) => p.id === successorId);
  const advice = p2Advised?.assessment;
  if (
    !advice ||
    advice.origin !== "fixture" ||
    advice.model_version !== "fixture-v1" ||
    !advice.limitations.some((l) => l.includes("Labelled fixture"))
  ) {
    fail("ADVICE", `Assessment contract mismatch: ${JSON.stringify(advice)}`);
  }
  const topCandidate = advice.suggestions[0]?.candidate_id;
  log("ASSESSMENT", `Fixture advice recorded (id=${advice.id}, topSuggestion=${topCandidate}).`);

  // Submit completion with a separate actual action
  log("RESULT", "Submitting completion result with action 'interval_compare'...");
  const resultReqId = `req-result-${Date.now()}`;
  const resultPayload = {
    contract_version: 1,
    request_id: resultReqId,
    page_id: successorId,
    expected_revision: p2Advised.revision,
    claim: claimToken,
    outcome: "complete",
    summary: "Synthetic investigation complete; interval examined.",
    evidence: [
      {
        id: "ev-acceptance-result",
        label: "Comparison outcome",
        value: "Synthetic: verified separate action selection",
        source: "Synthetic acceptance test runner",
        kind: "calculation",
        origin: "synthetic",
        state: "complete",
      },
    ],
    errors: [],
    action: {
      type: "interval_compare",
      assessment_id: advice.id,
    },
    worker: { kind: "agent", name: "test-eval-worker" },
  };
  const completeRes = await request(
    baseURL,
    "POST",
    "/api/work/submit_result",
    resultPayload,
    requestTimeoutMs,
  );
  if (!completeRes.ok) {
    fail("SUBMIT_RESULT", `submit_result failed: ${JSON.stringify(completeRes.data)}`);
  }
  const finalBook = completeRes.data;
  const p2Final = finalBook.pages.find((p) => p.id === successorId);
  const finalCont = finalBook.continuations.find((c) => c.id === continuationId);

  if (p2Final.status !== "ready" || p2Final.outcome !== "complete") {
    fail(
      "PAGE_READY",
      `Successor page not ready complete: status=${p2Final.status}, outcome=${p2Final.outcome}`,
    );
  }
  if (finalCont.state !== "completed") {
    fail("CONT_COMPLETED", `Continuation not marked completed: state=${finalCont.state}`);
  }
  if (p2Final.action?.type !== "interval_compare") {
    fail("ACTION", `Action type mismatch: ${JSON.stringify(p2Final.action)}`);
  }
  const independence = checkActionIndependence(p2Final.action, advice, explicitCandidates);
  log(
    "ACTION_VS_ADVICE",
    `Verified: actual action is '${independence.executedActionType}' (cited advice ${p2Final.action.assessment_id}), ` +
      `while advice top candidate was '${independence.topCandidateId}' (resolved action '${independence.topActionType}'). Model advice and worker action remain distinct.`,
  );

  // Deep-compare sealed Page 1 in completion snapshot
  checkLockedPageImmutability(
    finalBook.pages[0],
    originalLockedPage,
    "subsequent successor actions",
  );
  log("IMMUTABILITY", "Verified: locked Page 1 remained sealed and immutable throughout.");

  // Step 7: Verify result replay idempotence with complete snapshot equality
  log("IDEMPOTENCE", "Replaying identical result request ID to verify snapshot equality");
  const replayResult = await request(
    baseURL,
    "POST",
    "/api/work/submit_result",
    resultPayload,
    requestTimeoutMs,
  );
  if (!replayResult.ok || replayResult.status !== 200) {
    fail("RESULT_REPLAY", "Result replay was not idempotent.");
  }
  checkReplaySnapshotEquality(replayResult.data, finalBook, "Result replay");
  log(
    "IDEMPOTENCE",
    "Result replay verified completely identical across all pages, continuations, and events.",
  );

  console.log("\n================================================================================");
  log("PASS", "All HTTP acceptance verification checks passed successfully!");
  log("NOTE", "These checks verify backend contracts, atomic transitions, attempt fencing,");
  log("NOTE", "bounded retries, and history immutability over HTTP.");
  log("NOTE", "Interactive browser DOM observations and form events are verified separately.");
  console.log("================================================================================\n");

  return finalBook;
}

export async function main() {
  const targetUrl = process.argv[2] || process.env.BOOK_URL;
  try {
    await runAcceptance(targetUrl);
    process.exit(0);
  } catch (err) {
    console.error(`\n${err.message}\n`);
    process.exit(1);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main();
}
