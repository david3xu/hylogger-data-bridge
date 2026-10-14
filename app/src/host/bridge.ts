// Coordinate explicit chat follow-up and capability-gated authoritative handoff transport.
import {
  type Book,
  type Continuation,
  type DecisionChoice,
  type Handoff,
  isHandoff,
  isId,
  isTime,
  type Page,
} from "../state/contracts";

/**
 * Documented backend contract request for future automatic browser-to-host dispatch:
 * - Current HTTP routes (`GET /api/book`, `GET /api/events`, `POST /api/demo/start`,
 *   `POST /api/pages/{id}/decision`, `POST /api/pages/{id}/evidence`) persist a `pending`
 *   `Continuation` (`attempts: 0`, `claimed_by: null`, `lease_expires_at: null`).
 * - Leased worker `Handoff` creation (`events/claim.py`, `events/ack.py`, `pages/finish.py`)
 *   is an internal backend/worker operation and is not exposed as a browser HTTP route.
 * - The browser must never synthesize `attempt`, `lease_expires_at`, or fallback continuation/
 *   decision IDs. Until an agreed backend handoff operation and proven host transport exist,
 *   automatic host dispatch stays unavailable (`automaticDispatchAvailable: false`) and the
 *   reader provides explicit chat follow-up for committed human decisions.
 */
export const BACKEND_CONTRACT_REQUESTS = {
  authoritativeHandoffOperation: {
    status: "pending_backend_agreement" as const,
    summary:
      "Browser must obtain any leased Handoff from an authoritative backend operation rather than constructing attempts, leases, or fallback IDs locally.",
  },
} as const;

export type CommittedDecisionNotice = {
  kind: "decision_committed";
  contract_version: 1;
  run_id: string;
  page_id: string;
  successor_id: string;
  decision_id: string | null;
  continuation_id: string | null;
  continuation_state: Continuation["state"] | null;
  locked_revision: number;
  choice: DecisionChoice;
  note: string;
  evidence_ids: string[];
  recorded_at: string;
};

export type HostTransport = {
  readonly contractVersion: 1;
  readonly hostName: string;
  fetchAuthoritativeHandoff?: (pageId: string) => Promise<Handoff | null>;
  deliverHandoff?: (handoff: Handoff) => Promise<{ accepted: boolean; detail?: string }>;
  notifyDecisionCommitted?: (
    notice: CommittedDecisionNotice,
  ) => Promise<{ accepted: boolean; detail?: string }>;
};

export type HostCapability = {
  mode: "standalone" | "verified_host";
  available: boolean;
  automaticDispatchAvailable: boolean;
  hostName: string | null;
  detail: string;
};

export type HostDeliveryOutcome = {
  notified: boolean;
  accepted: boolean;
  mode: "standalone" | "verified_host";
  detail: string;
};

export type HostDeliveryState = {
  pageId: string;
  successorId: string;
  continuationId: string;
  decisionId: string;
  handoff: Handoff;
  status: "delivering" | "accepted" | "failed";
  error: string | null;
  attempts: number;
};

function isVerifiedTransport(candidate: unknown): candidate is HostTransport {
  if (typeof candidate !== "object" || candidate === null) return false;
  const record = candidate as Record<string, unknown>;
  const hasHandoffRoute =
    typeof record.fetchAuthoritativeHandoff === "function" &&
    typeof record.deliverHandoff === "function";
  const hasNoticeRoute = typeof record.notifyDecisionCommitted === "function";
  return (
    record.contractVersion === 1 &&
    typeof record.hostName === "string" &&
    record.hostName.trim().length > 0 &&
    (hasHandoffRoute || hasNoticeRoute)
  );
}

export function detectHostCapability(transport?: unknown): HostCapability {
  if (isVerifiedTransport(transport)) {
    const automaticDispatchAvailable =
      typeof transport.fetchAuthoritativeHandoff === "function" &&
      typeof transport.deliverHandoff === "function";
    return {
      mode: "verified_host",
      available: true,
      automaticDispatchAvailable,
      hostName: transport.hostName,
      detail: automaticDispatchAvailable
        ? `Connected to verified host transport (${transport.hostName} v1)`
        : `Host notification transport (${transport.hostName} v1) · automatic worker handoff unavailable without backend handoff endpoint`,
    };
  }
  return {
    mode: "standalone",
    available: false,
    automaticDispatchAvailable: false,
    hostName: null,
    detail: "Automatic host dispatch unavailable · use explicit chat follow-up",
  };
}

export function isCommittedDecisionNotice(value: unknown): value is CommittedDecisionNotice {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const rec = value as Record<string, unknown>;
  const keys = [
    "kind",
    "contract_version",
    "run_id",
    "page_id",
    "successor_id",
    "decision_id",
    "continuation_id",
    "continuation_state",
    "locked_revision",
    "choice",
    "note",
    "evidence_ids",
    "recorded_at",
  ];
  if (Object.keys(rec).length !== keys.length || !keys.every((k) => k in rec)) {
    return false;
  }
  if ("attempt" in rec || "lease_expires_at" in rec || "claimed_by" in rec) {
    return false;
  }
  return (
    rec.kind === "decision_committed" &&
    rec.contract_version === 1 &&
    isId(rec.run_id) &&
    isId(rec.page_id) &&
    isId(rec.successor_id) &&
    (rec.decision_id === null || isId(rec.decision_id)) &&
    (rec.continuation_id === null || isId(rec.continuation_id)) &&
    (rec.continuation_state === null ||
      ["pending", "running", "completed", "failed"].includes(String(rec.continuation_state))) &&
    typeof rec.locked_revision === "number" &&
    Number.isSafeInteger(rec.locked_revision) &&
    rec.locked_revision >= 0 &&
    ["accept", "modify", "reject"].includes(String(rec.choice)) &&
    typeof rec.note === "string" &&
    rec.note.length <= 4000 &&
    Array.isArray(rec.evidence_ids) &&
    rec.evidence_ids.every(isId) &&
    isTime(rec.recorded_at)
  );
}

export function buildCommittedDecisionNotice(
  book: Book | null,
  lockedPage: Page,
): CommittedDecisionNotice | null {
  if (!book || lockedPage.status !== "locked" || !lockedPage.decision) {
    return null;
  }
  if (lockedPage.decision.actor && lockedPage.decision.actor.kind !== "human") {
    return null;
  }
  const continuation = book.continuations?.find((item) => item.page_id === lockedPage.id);
  const successor = book.pages.find((item) => item.parent_id === lockedPage.id);
  const successorId =
    continuation?.successor_id ?? lockedPage.decision.successor_id ?? successor?.id ?? null;
  if (!successorId) {
    return null;
  }

  const notice: CommittedDecisionNotice = {
    kind: "decision_committed",
    contract_version: 1,
    run_id: book.run_id,
    page_id: lockedPage.id,
    successor_id: successorId,
    decision_id: lockedPage.decision.id ?? null,
    continuation_id: continuation?.id ?? null,
    continuation_state: continuation?.state ?? null,
    locked_revision: lockedPage.decision.locked_revision ?? lockedPage.revision,
    choice: lockedPage.decision.choice,
    note: lockedPage.decision.note,
    evidence_ids: lockedPage.decision.evidence_ids ?? lockedPage.evidence.map((item) => item.id),
    recorded_at: lockedPage.decision.recorded_at,
  };

  return isCommittedDecisionNotice(notice) ? notice : null;
}

export function formatChatFollowUp(notice: CommittedDecisionNotice): string {
  const refs = [
    `run=${notice.run_id}`,
    `page=${notice.page_id}@r${notice.locked_revision}`,
    `successor=${notice.successor_id}`,
    ...(notice.decision_id ? [`decision=${notice.decision_id}`] : []),
    ...(notice.continuation_id ? [`continuation=${notice.continuation_id}`] : []),
  ].join(" ");
  const notePart = notice.note.trim() ? ` — "${notice.note.trim()}"` : "";
  return `Continue HyLogger investigation (${refs}): choice=${notice.choice}${notePart}`;
}

export function hasBackendContinuationProgressed(
  book: Book | null,
  pageId: string,
  successorId?: string,
): boolean {
  if (!book) return false;
  const continuation = book.continuations?.find(
    (item) => item.page_id === pageId || (successorId && item.successor_id === successorId),
  );
  if (continuation) {
    if (
      continuation.state === "completed" ||
      continuation.state === "failed" ||
      continuation.acknowledged_at !== null
    ) {
      return true;
    }
  }
  const successor = book.pages.find(
    (item) => (successorId && item.id === successorId) || item.parent_id === pageId,
  );
  if (successor) {
    if (
      successor.status === "ready" ||
      successor.status === "locked" ||
      Boolean(successor.demo_running) ||
      successor.evidence.length > 0 ||
      Boolean(successor.action)
    ) {
      return true;
    }
  }
  return false;
}

export function verifyAuthoritativeHandoff(
  book: Book,
  lockedPage: Page,
  candidate: unknown,
): Handoff | null {
  if (!isHandoff(candidate)) {
    return null;
  }
  if (lockedPage.status !== "locked" || !lockedPage.decision) {
    return null;
  }
  if (lockedPage.decision.actor?.kind !== "human") {
    return null;
  }
  const continuation = book.continuations?.find((item) => item.page_id === lockedPage.id);
  if (!continuation) {
    return null;
  }
  if (hasBackendContinuationProgressed(book, lockedPage.id, continuation.successor_id)) {
    return null;
  }
  const matchesBackend =
    candidate.run_id === book.run_id &&
    candidate.page_id === lockedPage.id &&
    candidate.continuation_id === continuation.id &&
    candidate.decision_id === continuation.decision_id &&
    candidate.successor_id === continuation.successor_id &&
    candidate.locked_revision === continuation.locked_revision &&
    candidate.choice === lockedPage.decision.choice &&
    candidate.note === lockedPage.decision.note &&
    candidate.decided_at === lockedPage.decision.recorded_at &&
    (continuation.state === "pending" ||
      (continuation.state === "running" && continuation.attempts === candidate.attempt));

  return matchesBackend ? candidate : null;
}

export async function deliverAuthoritativeHandoff(
  handoff: Handoff,
  transport?: HostTransport,
): Promise<HostDeliveryOutcome> {
  if (!isHandoff(handoff)) {
    return {
      notified: false,
      accepted: false,
      mode: "standalone",
      detail: "Rejected handoff: payload does not satisfy the canonical v1 Handoff contract.",
    };
  }
  if (!isVerifiedTransport(transport) || typeof transport.deliverHandoff !== "function") {
    return {
      notified: false,
      accepted: false,
      mode: "standalone",
      detail: "Automatic host dispatch unavailable; use explicit chat follow-up.",
    };
  }
  try {
    const response = await transport.deliverHandoff(handoff);
    return {
      notified: true,
      accepted: Boolean(response?.accepted),
      mode: "verified_host",
      detail:
        response?.detail ??
        (response?.accepted
          ? `Host (${transport.hostName}) accepted authoritative handoff.`
          : `Host (${transport.hostName}) did not accept authoritative handoff.`),
    };
  } catch (failure) {
    return {
      notified: true,
      accepted: false,
      mode: "verified_host",
      detail:
        failure instanceof Error
          ? `Host delivery failed: ${failure.message}`
          : "Host delivery failed.",
    };
  }
}

export async function notifyCommittedDecision(
  notice: CommittedDecisionNotice,
  transport?: HostTransport,
): Promise<HostDeliveryOutcome> {
  if (!isCommittedDecisionNotice(notice)) {
    return {
      notified: false,
      accepted: false,
      mode: "standalone",
      detail: "Invalid committed-decision notification.",
    };
  }
  if (!isVerifiedTransport(transport) || typeof transport.notifyDecisionCommitted !== "function") {
    return {
      notified: false,
      accepted: false,
      mode: "standalone",
      detail: "Decision saved locally. Use explicit chat follow-up to continue in chat.",
    };
  }
  try {
    const response = await transport.notifyDecisionCommitted(notice);
    return {
      notified: true,
      accepted: Boolean(response?.accepted),
      mode: "verified_host",
      detail:
        response?.detail ??
        (response?.accepted
          ? `Host (${transport.hostName}) received committed-decision notification.`
          : `Host (${transport.hostName}) rejected committed-decision notification.`),
    };
  } catch (failure) {
    return {
      notified: true,
      accepted: false,
      mode: "verified_host",
      detail:
        failure instanceof Error
          ? `Committed-decision notification failed: ${failure.message}`
          : "Committed-decision notification failed.",
    };
  }
}
