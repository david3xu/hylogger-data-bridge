// Render the human workflow decision form with retry-safe state and sealed history records.
import type { DecisionChoice, Page } from "../state/contracts";
import type { DecisionDraft } from "../state/reader";

export const CHOICE_LABELS: Record<DecisionChoice, string> = {
  accept: "Continue with this evidence",
  modify: "Change the investigation",
  reject: "Set this candidate aside",
};

type DecisionFormProps = {
  page: Page;
  draft: DecisionDraft;
  busy: boolean;
  adviceDeclinedInView?: boolean;
  onChangeDraft: (choice: DecisionChoice, note: string) => void;
  onSubmitDecision: (choice: DecisionChoice, note: string) => Promise<boolean>;
};

export function DecisionForm({
  page,
  draft,
  busy,
  adviceDeclinedInView = false,
  onChangeDraft,
  onSubmitDecision,
}: DecisionFormProps) {
  const isRetry = draft.status === "failed" && Boolean(draft.requestId);

  return (
    <form
      className="review-box"
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmitDecision(draft.choice, draft.note);
      }}
    >
      <div className="section-heading">
        <span className="eyebrow">Your next step · human workflow decision</span>
        <span className="ready-dot">
          {isRetry ? "Submission failed · ready to retry" : "Ready for a workflow decision"}
        </span>
      </div>
      <h2>Where should this investigation go?</h2>
      <p className="quiet">
        Your choice seals this page and opens the next one. Geological findings remain unreviewed.
        {adviceDeclinedInView
          ? " Model advice is hidden in this browser view (local viewing preference only)."
          : ""}
      </p>

      {isRetry && (
        <div className="retry-preserve-box" role="alert">
          <strong>Exact input and request ID preserved for retry.</strong>
          <p>
            Request ID <code>{draft.requestId}</code> will be reused if you retry without changing
            your choice or note.
          </p>
        </div>
      )}

      <fieldset disabled={busy}>
        <legend className="visually-hidden">Choose the next direction</legend>
        <div className="decision-choices">
          {(["accept", "modify", "reject"] as const).map((item) => (
            <label className={draft.choice === item ? "choice selected" : "choice"} key={item}>
              <input
                type="radio"
                name={`choice-${page.id}`}
                value={item}
                checked={draft.choice === item}
                onChange={() => onChangeDraft(item, draft.note)}
              />
              <span>{CHOICE_LABELS[item]}</span>
            </label>
          ))}
        </div>
        <label className="note-label" htmlFor={`decision-note-${page.id}`}>
          Investigation note <span>(optional)</span>
        </label>
        <textarea
          id={`decision-note-${page.id}`}
          value={draft.note}
          onChange={(event) => onChangeDraft(draft.choice, event.target.value)}
          maxLength={2000}
          rows={3}
          placeholder="What should the next page examine?"
        />
        <div className="decision-footer">
          <small>This records your workflow choice, not geological approval.</small>
          <button type="submit" className="primary-button">
            {busy
              ? "Saving decision…"
              : isRetry
                ? "Retry decision & turn page"
                : "Record decision & turn page"}
            <span aria-hidden="true">↗</span>
          </button>
        </div>
      </fieldset>
    </form>
  );
}

export function SealedDecision({
  page,
  successorPage,
  onSelectPage,
}: {
  page: Page;
  successorPage?: Page;
  onSelectPage: (id: string) => void;
}) {
  if (!page.decision) return null;
  const actorKind = page.decision.actor?.kind;
  return (
    <section className="sealed-decision" aria-label="Recorded workflow decision">
      <div className="section-heading">
        <span className="eyebrow">Recorded workflow decision · immutable history</span>
        {actorKind && (
          <span className="actor-pill">
            Actor: {actorKind === "human" ? "human reviewer" : "unknown origin (legacy)"}
          </span>
        )}
      </div>
      <h2>{CHOICE_LABELS[page.decision.choice]}</h2>
      <p>{page.decision.note || "No additional note was recorded."}</p>
      <div className="sealed-footer">
        <small>
          Page sealed {new Date(page.decision.recorded_at).toLocaleString()} · Read-only history
          {page.decision.request_id ? ` · Request ${page.decision.request_id}` : ""}
        </small>
        {successorPage && (
          <button
            type="button"
            className="secondary-button"
            onClick={() => onSelectPage(successorPage.id)}
          >
            Open successor page ({String(successorPage.number).padStart(2, "0")}) →
          </button>
        )}
      </div>
    </section>
  );
}
