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

type DeliveryStatusBarProps = {
  delivery: ResolvedDelivery;
  busy?: boolean;
  onRetryHostDelivery?: (pageId: string) => void;
};

export function DeliveryStatusBar({
  delivery,
  busy = false,
  onRetryHostDelivery,
}: DeliveryStatusBarProps) {
  const [copied, setCopied] = useState(false);
  const activeKey = normalizedKey(delivery.state);
  const hostPageId = delivery.hostDeliveryPageId;

  const handleCopyFollowUp = () => {
    if (!delivery.chatFollowUp) return;
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(delivery.chatFollowUp).then(() => {
        setCopied(true);
      });
    } else {
      setCopied(true);
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
          <code className="chat-followup-code">{delivery.chatFollowUp}</code>
          <button type="button" className="secondary-button" onClick={handleCopyFollowUp}>
            {copied ? "Copied chat follow-up" : "Copy chat follow-up"}
          </button>
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
