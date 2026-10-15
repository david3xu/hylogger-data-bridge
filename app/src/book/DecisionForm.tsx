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
  draftSaveStatus?: "saved" | "unavailable" | null;
  onChangeDraft: (choice: DecisionChoice, note: string) => void;
  onSubmitDecision: (choice: DecisionChoice, note: string) => Promise<boolean>;
};

export function DecisionForm({
  page,
  draft,
  busy,
  adviceDeclinedInView = false,
  draftSaveStatus,
  onChangeDraft,
  onSubmitDecision,
}: DecisionFormProps) {
  const isRetry = draft.status === "failed" && Boolean(draft.requestId);

  return (
    <form
      className="review-box"
      onSubmit={(event) => {
        event.preventDefault();
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
        Add a note if needed, then choose an action below. Your action saves the decision and opens
        the next page. Geological findings remain unreviewed.
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
        <label className="note-label" htmlFor={`decision-note-${page.id}`}>
          Review note <span>(optional)</span>
        </label>
        <textarea
          id={`decision-note-${page.id}`}
          value={draft.note}
          onChange={(event) => onChangeDraft(draft.choice, event.target.value)}
          aria-describedby={`decision-note-help-${page.id}`}
          maxLength={2000}
          rows={3}
          placeholder="Reason for your choice, or intervals to examine next"
        />
        <p className="quiet" id={`decision-note-help-${page.id}`}>
          Automatically saved as a draft in this browser tab. Your chosen action commits the review
          for AI follow-up; typing alone does not start a new investigation step.
        </p>
        {draftSaveStatus && (
          <output className="draft-save-status" aria-live="polite">
            {draftSaveStatus === "saved"
              ? "Draft saved in this tab"
              : "Draft cannot be saved in this tab. Keep this page open until you choose an action."}
          </output>
        )}
        <div className="decision-choices">
          {(["accept", "modify", "reject"] as const).map((item) => (
            <button
              type="button"
              className={isRetry && draft.choice === item ? "choice selected" : "choice"}
              key={item}
              onClick={() => void onSubmitDecision(item, draft.note)}
            >
              <span>
                {isRetry && draft.choice === item ? "Retry: " : ""}
                {CHOICE_LABELS[item]}
              </span>
              <span aria-hidden="true">→</span>
            </button>
          ))}
        </div>
        <p className="quiet">This records your workflow choice, not geological approval.</p>
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
