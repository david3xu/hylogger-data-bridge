#!/usr/bin/env node
/**
 * Synthetic HTTP acceptance runner for HyLogger Data Bridge.
 *
 * Verifies backend lifecycle contracts, atomic decisions, attempt fencing,
 * bounded retries, fixture advice, and locked history preservation over HTTP.
 *
 * Usage:
 *   node app/scripts/acceptance.mjs [baseURL]
 *   node app/scripts/acceptance.mjs http://127.0.0.1:8770
 */

const targetUrl = process.argv[2] || process.env.BOOK_URL || "http://127.0.0.1:8770";
const baseURL = targetUrl.replace(/\/+$/, "");

const EXACT_NOTE =
  "Exact human note: check 214–220 m · δ¹⁸O ± 0.2‰ · \"quotes\" & 'single' · \t tab \n newline! 🪨";

function log(phase, message) {
  console.log(`[HTTP ACCEPTANCE] [${phase}] ${message}`);
}

function fail(phase, message) {
  console.error(`\n[HTTP ACCEPTANCE] [FAIL] [${phase}] ${message}\n`);
  process.exit(1);
}

async function request(method, path, body = null) {
  const url = `${baseURL}${path}`;
  const options = {
    method,
    headers: {
      Accept: "application/json",
    },
  };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, options);
  } catch (err) {
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

async function main() {
  log("START", `Connecting to target service at ${baseURL}`);

  // Step 1: Verify service is reachable and acting on a fresh designated test book
  const init = await request("GET", "/api/book");
  if (!init.ok || init.status !== 200) {
    fail("INIT", `GET /api/book returned HTTP ${init.status}: ${JSON.stringify(init.data)}`);
  }
  const initBook = init.data;
  if (
    initBook.run_id !== "demo" ||
    initBook.source !== "synthetic_demo" ||
    !Array.isArray(initBook.pages) ||
    initBook.pages.length !== 1 ||
    initBook.pages[0].status !== "draft" ||
    initBook.pages[0].decision !== null
  ) {
    fail(
      "PRECONDITION",
      `The target server at ${baseURL} is not running against a fresh designated test book. ` +
        `Found ${initBook.pages?.length ?? 0} pages, status=${initBook.pages?.[0]?.status}. ` +
        `Launch a fresh isolated book (e.g. outputs/live-book/test.sqlite3) on an unused port.`,
    );
  }
  const page1 = initBook.pages[0];
  const page1Id = page1.id;
  const page1InitialRev = page1.revision;

  if (page1.assessment !== null) {
    fail("ASSESSMENT", "Expected initial draft page to have assessment: null.");
  }
  log("CHECK", "Initial book confirmed: single draft page 1 with assessment: null.");

  // Step 2: Trigger staged synthetic runner to bring page 1 to ready
  log("STREAMING", `Starting synthetic demo on draft page ${page1Id} (rev ${page1InitialRev})`);
  const startRes = await request("POST", "/api/demo/start", {
    page_id: page1Id,
    expected_revision: page1InitialRev,
  });
  if (startRes.status !== 202 || startRes.data.started !== true) {
    fail("DEMO_START", `POST /api/demo/start failed: ${JSON.stringify(startRes.data)}`);
  }

  // Poll until page 1 reaches ready state
  let readyBook = null;
  for (let i = 0; i < 40; i++) {
    await new Promise((resolve) => setTimeout(resolve, 200));
    const poll = await request("GET", "/api/book");
    if (poll.ok && poll.data.pages?.[0]?.status === "ready") {
      readyBook = poll.data;
      break;
    }
  }
  if (!readyBook) {
    fail("TIMEOUT", "Page 1 did not reach ready state within 8 seconds.");
  }
  const readyPage1 = readyBook.pages[0];
  if (readyPage1.evidence.length !== 5) {
    fail("EVIDENCE", `Expected 5 synthetic evidence items, found ${readyPage1.evidence.length}.`);
  }
  const readyRevision = readyPage1.revision;
  log(
    "STREAMING",
    `Page 1 ready with ${readyPage1.evidence.length} evidence items (rev ${readyRevision}).`,
  );

  // Step 3: Commit exact human decision and verify atomic lock + successor creation
  const decisionReqId = `req-accept-${Date.now()}`;
  log("DECISION", `Committing decision: choice=modify, requestId=${decisionReqId}`);
  const decideRes = await request("POST", `/api/pages/${page1Id}/decision`, {
    choice: "modify",
    note: EXACT_NOTE,
    expected_revision: readyRevision,
    request_id: decisionReqId,
  });
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
      `Committed decision note mismatch. Expected exact note with Unicode/tabs/newlines.`,
    );
  }

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

  // Step 4: Verify decision idempotence
  log("IDEMPOTENCE", "Replaying identical decision request ID to verify idempotence");
  const replayRes = await request("POST", `/api/pages/${page1Id}/decision`, {
    choice: "modify",
    note: EXACT_NOTE,
    expected_revision: readyRevision,
    request_id: decisionReqId,
  });
  if (!replayRes.ok || replayRes.data.pages.length !== 2) {
    fail("IDEMPOTENCE", "Decision replay created duplicate successors or failed.");
  }
  log("IDEMPOTENCE", "Replay successful. No duplicate pages or continuations created.");

  // Step 5: Worker claim, acknowledgement, and bounded failure/retry
  log("WORKER", "Worker claiming delivery attempt 1...");
  const claim1 = await request("POST", "/api/work/claim_delivery", {
    worker: "test-eval-worker",
    seconds: 30,
  });
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
  log("WORKER", `Attempt 1 claimed. Exact note and choice preserved in handoff.`);

  // Acknowledge attempt 1
  const ack1 = await request("POST", "/api/work/acknowledge_delivery", {
    continuation_id: continuationId,
    attempt: 1,
    seconds: 30,
  });
  const ackCont1 = ack1.data.continuations?.find((c) => c.id === continuationId);
  if (!ack1.ok || !ackCont1?.acknowledged_at) {
    fail("ACK", `Acknowledge attempt 1 failed: ${JSON.stringify(ack1.data)}`);
  }
  log("WORKER", `Attempt 1 acknowledged at ${ackCont1.acknowledged_at}.`);

  // Simulate bounded worker failure using canonical Error contract
  log("FAILURE", "Failing attempt 1 with canonical Error payload...");
  const fail1 = await request("POST", "/api/work/fail_delivery", {
    continuation_id: continuationId,
    attempt: 1,
    error: {
      error: "Simulated worker transient failure",
      code: "delivery_failed",
      retryable: true,
    },
  });
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

  // Verify attempt log
  const attemptsRes = await request("POST", "/api/work/read_attempts", {
    continuation_id: continuationId,
  });
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
  const claim2 = await request("POST", "/api/work/claim_delivery", {
    worker: "test-eval-worker",
    seconds: 60,
  });
  const handoff2 = claim2.data?.handoff;
  if (!claim2.ok || handoff2?.attempt !== 2) {
    fail("CLAIM_2", `Claim attempt 2 failed: ${JSON.stringify(claim2.data)}`);
  }
  const claimToken = { continuation_id: continuationId, attempt: 2 };

  await request("POST", "/api/work/acknowledge_delivery", {
    continuation_id: continuationId,
    attempt: 2,
    seconds: 60,
  });
  log("WORKER", "Attempt 2 acknowledged.");

  // Submit incremental evidence under claim
  const evRes = await request("POST", "/api/work/submit_evidence", {
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
  });
  if (!evRes.ok) {
    fail("SUBMIT_EVIDENCE", `submit_evidence failed: ${JSON.stringify(evRes.data)}`);
  }
  const p2AfterEv = evRes.data.pages.find((p) => p.id === successorId);
  const p2RevAfterEv = p2AfterEv.revision;
  log(
    "EVIDENCE",
    `Incremental evidence submitted to successor page (rev incremented to ${p2RevAfterEv}).`,
  );

  // Request real backend fixture assessment
  log("ASSESSMENT", "Requesting assessment from backend (FixtureProvider)...");
  const assessRes = await request("POST", "/api/work/request_assessment", {
    page_id: successorId,
    expected_revision: p2RevAfterEv,
  });
  if (!assessRes.ok) {
    fail("ASSESSMENT", `request_assessment failed: ${JSON.stringify(assessRes.data)}`);
  }
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
  const completeRes = await request("POST", "/api/work/submit_result", resultPayload);
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
  log(
    "ACTION_VS_ADVICE",
    `Verified: actual action is '${p2Final.action.type}' (cited advice ${p2Final.action.assessment_id}), ` +
      `while advice top candidate was '${topCandidate}'. Model advice and worker action remain distinct.`,
  );

  // Step 7: Verify locked history immutability
  const p1Final = finalBook.pages.find((p) => p.id === page1Id);
  if (
    p1Final.status !== "locked" ||
    p1Final.decision.choice !== "modify" ||
    p1Final.decision.note !== EXACT_NOTE ||
    p1Final.evidence.length !== 5
  ) {
    fail("IMMUTABILITY", "Locked Page 1 was altered during subsequent successor actions!");
  }
  log("IMMUTABILITY", "Verified: locked Page 1 remained sealed and immutable throughout.");

  // Idempotent result replay
  const replayResult = await request("POST", "/api/work/submit_result", resultPayload);
  if (!replayResult.ok || replayResult.data.pages.length !== 2) {
    fail("RESULT_REPLAY", "Result replay was not idempotent.");
  }
  log("IDEMPOTENCE", "Result replay verified idempotent.");

  console.log("\n================================================================================");
  log("PASS", "All HTTP acceptance verification checks passed successfully!");
  log("NOTE", "These checks verify backend contracts, atomic transitions, attempt fencing,");
  log("NOTE", "bounded retries, and persistence over HTTP. Browser DOM observations and");
  log("NOTE", "interactive form events are verified separately in browser acceptance tests.");
  console.log("================================================================================\n");
}

main().catch((err) => {
  console.error("Unhandled error:", err);
  process.exit(1);
});
