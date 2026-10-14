// Render honest, backend-confirmed delivery and continuation states with explicit chat follow-up.
import { useState } from "react";
import type { DeliveryState } from "../state/contracts";
import type { ResolvedDelivery } from "../state/delivery";

const PIPELINE_STEPS: ReadonlyArray<{ key: DeliveryState; label: string }> = [
  { key: "saved", label: "Saved" },
  { key: "pending_delivery", label: "Pending delivery" },
  { key: "accepted", label: "Accepted by agent" },
  { key: "working", label: "Working" },
  { key: "failed", label: "Failed / needs input" },
  { key: "ready", label: "Ready" },
];

function normalizedKey(state: DeliveryState): DeliveryState {
  return state === "needs_input" ? "failed" : state;
}

export type ClipboardLike = {
  clipboard?: {
    writeText?: (value: string) => Promise<void>;
  };
};

export async function copyTextToClipboard(
  text: string,
  nav: ClipboardLike | undefined = typeof navigator !== "undefined" ? navigator : undefined,
): Promise<{ ok: boolean; error: string | null }> {
  if (!nav?.clipboard || typeof nav.clipboard.writeText !== "function") {
    return {
      ok: false,
      error:
        "Clipboard access is unavailable in this browser. Select and copy the follow-up text below.",
    };
  }
  try {
    await nav.clipboard.writeText(text);
    return { ok: true, error: null };
  } catch (failure) {
    const reason =
      failure instanceof Error && failure.message.trim().length > 0
        ? `Clipboard copy failed (${failure.message}).`
        : "Clipboard permission was denied.";
    return {
      ok: false,
      error: `${reason} Select and copy the follow-up text below.`,
    };
  }
}

type DeliveryStatusBarProps = {
  delivery: ResolvedDelivery;
  busy?: boolean;
  initialCopyError?: string | null;
  onRetryHostDelivery?: (pageId: string) => void;
};

export function DeliveryStatusBar({
  delivery,
  busy = false,
  initialCopyError = null,
  onRetryHostDelivery,
}: DeliveryStatusBarProps) {
  const [copyState, setCopyState] = useState<{
    status: "idle" | "copied" | "failed";
    error: string | null;
    forText: string | null;
  }>({
    status: initialCopyError ? "failed" : "idle",
    error: initialCopyError,
    forText: delivery.chatFollowUp ?? null,
  });

  const activeKey = normalizedKey(delivery.state);
  const hostPageId = delivery.hostDeliveryPageId;

  const isSameText = copyState.forText === (delivery.chatFollowUp ?? null);
  const effectiveStatus = isSameText ? copyState.status : initialCopyError ? "failed" : "idle";
  const effectiveError = isSameText ? copyState.error : initialCopyError;

  const handleCopyFollowUp = async () => {
    const targetText = delivery.chatFollowUp;
    if (!targetText) return;
    const outcome = await copyTextToClipboard(targetText);
    if (outcome.ok) {
      setCopyState({
        status: "copied",
        error: null,
        forText: targetText,
      });
    } else {
      setCopyState({
        status: "failed",
        error: outcome.error,
        forText: targetText,
      });
    }
  };

  return (
    <section
      className={`delivery-panel delivery-${activeKey}`}
      aria-label="Backend delivery status"
    >
      <div className="section-heading">
        <span className="eyebrow">
          Delivery &amp; continuation state ·{" "}
          {delivery.confirmedByBackend ? "Backend confirmed" : "Needs retry / input"}
        </span>
        <span className={`delivery-badge state-${activeKey}`}>{delivery.label}</span>
      </div>
      <ol className="delivery-steps" aria-label="Delivery stages">
        {PIPELINE_STEPS.map((step) => {
          const isCurrent = step.key === activeKey;
          return (
            <li
              key={step.key}
              aria-current={isCurrent ? "step" : undefined}
              className={`delivery-step ${isCurrent ? "current" : ""}`}
            >
              {step.label}
            </li>
          );
        })}
      </ol>
      <p className="delivery-summary">
        <strong>{delivery.summary}.</strong> {delivery.detail}
      </p>
      {delivery.chatFollowUp && (
        <section className="chat-followup-row" aria-label="Explicit chat follow-up">
          <div className="chat-followup-main">
            <code className="chat-followup-code">{delivery.chatFollowUp}</code>
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                void handleCopyFollowUp();
              }}
            >
              {effectiveStatus === "copied"
                ? "Copied chat follow-up"
                : effectiveStatus === "failed"
                  ? "Retry copy chat follow-up"
                  : "Copy chat follow-up"}
            </button>
          </div>
          {effectiveStatus === "failed" && effectiveError && (
            <div className="chat-followup-fallback-box" role="alert">
              <p className="chat-followup-error">{effectiveError}</p>
              <label className="visually-hidden" htmlFor="chat-followup-fallback-input">
                Selectable chat follow-up text
              </label>
              <input
                id="chat-followup-fallback-input"
                type="text"
                readOnly
                className="chat-followup-fallback"
                aria-label="Selectable chat follow-up text"
                value={delivery.chatFollowUp}
                onFocus={(event) => event.currentTarget.select()}
              />
            </div>
          )}
        </section>
      )}
      {(delivery.continuationId ||
        delivery.requestId ||
        delivery.attemptCount !== undefined ||
        (delivery.retryableHostDelivery && hostPageId && onRetryHostDelivery)) && (
        <div className="delivery-footer-row">
          <small className="delivery-meta">
            {delivery.continuationId && <span>Continuation: {delivery.continuationId}</span>}
            {delivery.requestId && (
              <span>
                {delivery.continuationId ? " · " : ""}Request ID: {delivery.requestId}
              </span>
            )}
            {delivery.attemptCount !== undefined && (
              <span>
                {delivery.continuationId || delivery.requestId ? " · " : ""}Attempts:{" "}
                {delivery.attemptCount}
                {delivery.maxAttempts !== undefined ? `/${delivery.maxAttempts}` : ""}
              </span>
            )}
          </small>
          {delivery.retryableHostDelivery && hostPageId && onRetryHostDelivery && (
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => onRetryHostDelivery(hostPageId)}
            >
              {busy ? "Retrying host handoff…" : "Retry host delivery"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
