// Map canonical Book.continuations, page outcomes, and host handoffs into presentation states.
import {
  buildCommittedDecisionNotice,
  type CommittedDecisionNotice,
  formatChatFollowUp,
  type HostDeliveryState,
} from "../host/bridge";
import type { Book, Continuation, DeliveryState, Page } from "./contracts";
import { canDispatchHostHandoff, type DecisionDraft, isHostDeliveryObsolete } from "./reader";

export type ResolvedDelivery = {
  state: DeliveryState;
  label: string;
  summary: string;
  detail: string;
  requestId?: string;
  continuationId?: string;
  attemptCount?: number;
  maxAttempts?: number;
  confirmedByBackend: boolean;
  retryableDecision: boolean;
  retryableHostDelivery: boolean;
  hostDeliveryPageId?: string;
  committedNotice?: CommittedDecisionNotice;
  chatFollowUp?: string;
};

const STATE_LABELS: Record<DeliveryState, string> = {
  saved: "Saved",
  pending_delivery: "Pending delivery",
  accepted: "Accepted by agent",
  working: "Working",
  failed: "Failed / needs input",
  needs_input: "Failed / needs input",
  ready: "Ready",
};

function hasInterruptedEvent(book: Book | null, page: Page): boolean {
  if (!book || page.status !== "draft" || page.demo_running) return false;
  const pageEvents = book.events.filter((event) => event.page_id === page.id);
  const lastLifecycle = [...pageEvents]
    .reverse()
    .find((event) => ["demo_interrupted", "demo_started", "page_ready"].includes(event.type));
  return (
    lastLifecycle?.type === "demo_interrupted" ||
    page.progress.toLowerCase().includes("interrupted")
  );
}

export function findContinuationForPage(book: Book | null, page: Page): Continuation | undefined {
  if (!book?.continuations || book.continuations.length === 0) {
    return undefined;
  }
  if (page.status === "locked") {
    return book.continuations.find((item) => item.page_id === page.id);
  }
  return (
    book.continuations.find((item) => item.successor_id === page.id) ??
    book.continuations.find((item) => item.page_id === page.id)
  );
}

function findCommittedNoticeForPage(
  book: Book | null,
  page: Page,
): CommittedDecisionNotice | undefined {
  if (!book) return undefined;
  if (page.status === "locked") {
    return buildCommittedDecisionNotice(book, page) ?? undefined;
  }
  if (page.parent_id) {
    const parent = book.pages.find((item) => item.id === page.parent_id);
    if (parent) {
      return buildCommittedDecisionNotice(book, parent) ?? undefined;
    }
  }
  return undefined;
}

export function resolveDelivery(
  book: Book | null,
  page: Page,
  draft?: DecisionDraft,
  hostDelivery?: HostDeliveryState,
): ResolvedDelivery {
  const isLive = book?.source === "live";
  const activeHostDelivery =
    hostDelivery && book && isHostDeliveryObsolete(book, hostDelivery) ? undefined : hostDelivery;
  const committedNotice = findCommittedNoticeForPage(book, page);
  const chatFollowUp = committedNotice ? formatChatFollowUp(committedNotice) : undefined;

  if (draft?.status === "failed" && page.status !== "locked") {
    return {
      state: "failed",
      label: STATE_LABELS.failed,
      summary: "Decision not yet confirmed by backend",
      detail:
        draft.error ?? "Submission failed. Retry with the preserved request ID or review the page.",
      requestId: draft.requestId || undefined,
      confirmedByBackend: false,
      retryableDecision: true,
      retryableHostDelivery: false,
    };
  }

  if (
    page.status === "ready" &&
    (page.outcome === "failed" || (page.errors && page.errors.length > 0))
  ) {
    const firstError = page.errors?.[0];
    return {
      state: "failed",
      label: STATE_LABELS.failed,
      summary: "Worker reported a failure; human workflow input required",
      detail: firstError
        ? `${firstError.error} (${firstError.code})`
        : page.progress || page.summary,
      confirmedByBackend: true,
      retryableDecision: false,
      retryableHostDelivery: false,
    };
  }

  const continuation = findContinuationForPage(book, page);

  if (
    activeHostDelivery?.status === "failed" &&
    canDispatchHostHandoff(book, activeHostDelivery.pageId, activeHostDelivery)
  ) {
    return {
      state: "failed",
      label: STATE_LABELS.failed,
      summary: "Decision saved locally, but host handoff delivery failed",
      detail:
        activeHostDelivery.error ??
        "The host transport did not accept the authoritative handoff. Retry host delivery or use explicit chat follow-up.",
      requestId: page.decision?.request_id ?? committedNotice?.decision_id ?? undefined,
      continuationId: activeHostDelivery.continuationId,
      attemptCount: activeHostDelivery.attempts,
      maxAttempts: continuation?.max_attempts,
      confirmedByBackend: true,
      retryableDecision: false,
      retryableHostDelivery: true,
      hostDeliveryPageId: activeHostDelivery.pageId,
      committedNotice,
      chatFollowUp,
    };
  }

  if (continuation) {
    return resolveFromContinuation(
      book,
      page,
      continuation,
      activeHostDelivery,
      committedNotice,
      chatFollowUp,
    );
  }

  if (activeHostDelivery?.status === "accepted") {
    return {
      state: "accepted",
      label: STATE_LABELS.accepted,
      summary: "Host transport acknowledged authoritative handoff",
      detail: "Verified host transport accepted the handoff.",
      requestId: page.decision?.request_id,
      continuationId: activeHostDelivery.continuationId,
      attemptCount: activeHostDelivery.attempts,
      confirmedByBackend: true,
      retryableDecision: false,
      retryableHostDelivery: false,
      committedNotice,
      chatFollowUp,
    };
  }

  if (page.status === "ready") {
    return {
      state: "ready",
      label: STATE_LABELS.ready,
      summary:
        page.outcome === "partial"
          ? "Partial evidence ready for human workflow decision"
          : "Evidence ready for human workflow decision",
      detail: page.progress || "Review the evidence and record your workflow decision.",
      confirmedByBackend: true,
      retryableDecision: false,
      retryableHostDelivery: false,
    };
  }

  if (page.status === "locked") {
    const isUnknownActor = page.decision?.actor?.kind === "unknown";
    return {
      state: "saved",
      label: STATE_LABELS.saved,
      summary: isUnknownActor
        ? "Historical decision saved (unknown actor origin; never dispatched)"
        : "Decision saved in SQLite and page locked",
      detail: isUnknownActor
        ? "Legacy record without human actor attribution; preserved as immutable history."
        : "Decision is persisted locally. Automatic host dispatch is unavailable until a backend handoff operation is agreed; use explicit chat follow-up.",
      requestId: page.decision?.request_id,
      confirmedByBackend: true,
      retryableDecision: false,
      retryableHostDelivery: false,
      committedNotice,
      chatFollowUp,
    };
  }

  if (page.demo_running) {
    return {
      state: "working",
      label: STATE_LABELS.working,
      summary: isLive
        ? "Worker collecting investigation evidence"
        : "Worker collecting synthetic evidence",
      detail:
        page.progress ||
        (isLive
          ? "Running investigation step and streaming committed evidence."
          : "Running synthetic example and streaming committed evidence."),
      confirmedByBackend: true,
      retryableDecision: false,
      retryableHostDelivery: false,
    };
  }

  if (hasInterruptedEvent(book, page)) {
    return {
      state: "failed",
      label: STATE_LABELS.failed,
      summary: "Worker interrupted; needs user action to resume",
      detail: page.progress || "Run interrupted; resume to continue without duplicate pages.",
      confirmedByBackend: true,
      retryableDecision: false,
      retryableHostDelivery: false,
    };
  }

  return {
    state: "saved",
    label: STATE_LABELS.saved,
    summary:
      page.parent_id !== null
        ? "Successor draft saved; awaiting worker or explicit follow-up"
        : "Draft page saved locally",
    detail:
      page.parent_id !== null
        ? isLive
          ? "Parent decision was saved locally. Use explicit chat follow-up or wait for a worker write."
          : "Parent decision was saved locally. Start the synthetic case or use explicit chat follow-up."
        : page.progress ||
          (isLive
            ? "Waiting for investigation evidence to be recorded."
            : "Ready to start the synthetic example."),
    confirmedByBackend: true,
    retryableDecision: false,
    retryableHostDelivery: false,
    committedNotice,
    chatFollowUp,
  };
}

function resolveFromContinuation(
  book: Book | null,
  page: Page,
  continuation: Continuation,
  hostDelivery?: HostDeliveryState,
  committedNotice?: CommittedDecisionNotice,
  chatFollowUp?: string,
): ResolvedDelivery {
  const isLive = book?.source === "live";
  const successor = book?.pages.find((item) => item.id === continuation.successor_id);
  const meta = {
    requestId: page.decision?.request_id,
    continuationId: continuation.id,
    attemptCount: continuation.attempts,
    maxAttempts: continuation.max_attempts,
    confirmedByBackend: true,
    retryableDecision: false,
    retryableHostDelivery: false,
    committedNotice,
    chatFollowUp,
  };

  if (continuation.state === "completed") {
    if (page.status === "ready" || successor?.status === "ready") {
      return {
        ...meta,
        state: "ready",
        label: STATE_LABELS.ready,
        summary: "Continuation completed and evidence ready for review",
        detail: page.progress || "Review the evidence and record your workflow decision.",
        committedNotice: undefined,
        chatFollowUp: undefined,
      };
    }
    if (page.demo_running) {
      return {
        ...meta,
        state: "working",
        label: STATE_LABELS.working,
        summary: isLive
          ? "Worker collecting investigation evidence"
          : "Worker collecting synthetic evidence",
        detail: page.progress || "Streaming committed evidence to this page.",
        committedNotice: undefined,
        chatFollowUp: undefined,
      };
    }
    return {
      ...meta,
      state: "ready",
      label: STATE_LABELS.ready,
      summary: `Continuation completed on Page ${successor ? String(successor.number).padStart(2, "0") : continuation.successor_id}`,
      detail: `Acknowledged at ${continuation.acknowledged_at} and worker result applied.`,
      committedNotice: undefined,
      chatFollowUp: undefined,
    };
  }

  if (page.status === "ready") {
    return {
      ...meta,
      state: "ready",
      label: STATE_LABELS.ready,
      summary:
        page.outcome === "partial"
          ? "Partial evidence ready for human workflow decision"
          : "Evidence ready for human workflow decision",
      detail: page.progress || "Review the evidence and record your workflow decision.",
      committedNotice: undefined,
      chatFollowUp: undefined,
    };
  }

  if (continuation.state === "failed") {
    const errText = continuation.last_error
      ? `${continuation.last_error.error} (${continuation.last_error.code})`
      : "Continuation failed after maximum attempts.";
    return {
      ...meta,
      state: "failed",
      label: STATE_LABELS.failed,
      summary: `Continuation delivery failed (${continuation.attempts}/${continuation.max_attempts} attempts)`,
      detail: errText,
    };
  }

  if (continuation.state === "pending") {
    if (hostDelivery?.status === "accepted" || continuation.acknowledged_at !== null) {
      return {
        ...meta,
        state: "accepted",
        label: STATE_LABELS.accepted,
        summary: "Decision handoff accepted by agent host",
        detail: page.progress || "Host acknowledged handoff; awaiting worker completion.",
      };
    }
    if (page.demo_running) {
      return {
        ...meta,
        state: "working",
        label: STATE_LABELS.working,
        summary: isLive
          ? "Worker collecting investigation evidence"
          : "Worker collecting synthetic evidence",
        detail: page.progress || "Streaming committed evidence to this page.",
      };
    }
    const retryNote = continuation.last_error
      ? `Last attempt error: ${continuation.last_error.error} (${continuation.last_error.code}).`
      : "Queued in Book.continuations awaiting worker claim or explicit chat follow-up.";
    return {
      ...meta,
      state: "pending_delivery",
      label: STATE_LABELS.pending_delivery,
      summary:
        continuation.attempts > 0
          ? `Pending delivery retry (attempt ${continuation.attempts}/${continuation.max_attempts})`
          : "Decision committed; pending delivery to agent",
      detail: retryNote,
    };
  }

  // continuation.state === "running"
  if (page.demo_running || page.status === "draft") {
    if (continuation.acknowledged_at !== null && !page.demo_running && page.evidence.length === 0) {
      return {
        ...meta,
        state: "accepted",
        label: STATE_LABELS.accepted,
        summary: `Accepted by ${continuation.claimed_by ?? "agent"}`,
        detail: page.progress || "Agent acknowledged handoff and holds an active lease.",
      };
    }
    return {
      ...meta,
      state: "working",
      label: STATE_LABELS.working,
      summary: `Working · claimed by ${continuation.claimed_by ?? "worker"} (attempt ${continuation.attempts}/${continuation.max_attempts})`,
      detail: page.progress || "Worker actively executing investigation turn under lease.",
    };
  }
  return {
    ...meta,
    state: "working",
    label: STATE_LABELS.working,
    summary: `Continuation running · claimed by ${continuation.claimed_by ?? "worker"}`,
    detail: `Lease active until ${continuation.lease_expires_at ?? "completion"}.`,
  };
}
