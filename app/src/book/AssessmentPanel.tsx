// Present canonical v1 model advice separately from scientific evidence, actions, and decisions.
import type { ResolvedAssessment } from "../state/assessment";

type AssessmentPanelProps = {
  resolved: ResolvedAssessment;
  pageRevision: number;
  onToggleDecline: (declined: boolean) => void;
};

export function AssessmentPanel({ resolved, pageRevision, onToggleDecline }: AssessmentPanelProps) {
  const {
    assessment,
    status,
    badgeLabel,
    isStale,
    declinedInView,
    referencedEvidenceIds,
    actualAction,
  } = resolved;

  if (assessment === null) {
    return (
      <section
        className={`assessment-panel status-${status}`}
        aria-label="Local decision-model advice"
      >
        <div className="section-heading">
          <span className="eyebrow">Local decision-model advice · separate from evidence</span>
          <div className="assessment-badges">
            <span className="assessment-badge badge-none">{badgeLabel}</span>
          </div>
        </div>
        <p className="small-detail">No assessment recorded.</p>
        <div className="actual-action-box">
          <span className="eyebrow">Actual action / runtime state (separate from advice)</span>
          <p>{actualAction}</p>
        </div>
      </section>
    );
  }

  return (
    <section
      className={`assessment-panel status-${status} ${declinedInView ? "is-declined" : ""}`}
      aria-label="Local decision-model advice"
    >
      <div className="section-heading">
        <span className="eyebrow">Local decision-model advice · separate from evidence</span>
        <div className="assessment-badges">
          <span className={`assessment-badge badge-${status}`}>{badgeLabel}</span>
          {declinedInView && (
            <span className="assessment-badge badge-declined">
              Declined in this view (local preference)
            </span>
          )}
        </div>
      </div>

      {isStale && (
        <output className="assessment-warning">
          <strong>Stale assessment:</strong> Computed at revision {assessment.state_revision}, while
          this page is at revision {pageRevision}. Newer evidence arrived after this advice was
          generated.
        </output>
      )}

      {status === "unavailable" && (
        <output className="assessment-warning unavailable-notice">
          <strong>Assessment unavailable:</strong> The backend recorded an unavailable assessment
          for this state.
        </output>
      )}

      <div className="assessment-provenance">
        <span>
          <strong>Origin:</strong> {assessment.origin}
        </span>
        <span>
          <strong>Status:</strong> {assessment.status}
        </span>
        <span>
          <strong>Model:</strong> {assessment.model_version}
        </span>
        <span>
          <strong>Assessment revision:</strong> {assessment.state_revision} (page revision{" "}
          {pageRevision})
        </span>
        <span>
          <strong>ID:</strong> {assessment.id}
        </span>
        <span title={assessment.request_hash}>
          <strong>Request hash:</strong> {assessment.request_hash.slice(0, 12)}…
        </span>
      </div>

      <div className="actual-action-box">
        <span className="eyebrow">Actual action / runtime state (separate from advice)</span>
        <p>{actualAction}</p>
      </div>

      {declinedInView ? (
        <div className="declined-notice">
          <p>
            <strong>Model advice declined in this browser view (local preference).</strong> This is
            a local viewing preference and is not recorded as part of the immutable page history.
          </p>
        </div>
      ) : (
        assessment.suggestions.length > 0 && (
          <div className="suggestions-block">
            <span className="eyebrow">Ranked candidate suggestions (advisory only)</span>
            <ol className="suggestion-list">
              {assessment.suggestions.map((item) => (
                <li key={`${item.rank}-${item.candidate_id}`} className="suggestion-item">
                  <div className="suggestion-header">
                    <strong>
                      #{item.rank} · {item.candidate_id}
                    </strong>
                    {item.evidence_ids.length > 0 && (
                      <span className="suggestion-score">
                        cites: {item.evidence_ids.join(", ")}
                      </span>
                    )}
                  </div>
                  <p>{item.rationale}</p>
                </li>
              ))}
            </ol>
          </div>
        )
      )}

      <div className="assessment-details-grid">
        <div>
          <span className="eyebrow">Referenced evidence</span>
          <p className="small-detail">
            {referencedEvidenceIds.length > 0
              ? referencedEvidenceIds.join(", ")
              : "None referenced at this revision"}
          </p>
        </div>
        <div>
          <span className="eyebrow">Evidence gaps</span>
          {assessment.evidence_gaps.length > 0 ? (
            <ul className="compact-list">
              {assessment.evidence_gaps.map((gap) => (
                <li key={gap}>{gap}</li>
              ))}
            </ul>
          ) : (
            <p className="small-detail">None reported</p>
          )}
        </div>
      </div>

      <div className="assessment-footer-meta">
        <p className="small-detail">
          <strong>Uncertainty:</strong> {assessment.uncertainty ?? "Not reported (null)"}
        </p>
        <ul className="compact-list limitations-list">
          {assessment.limitations.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
      </div>

      <div className="assessment-actions">
        <small className="quiet">
          Model advice is not execution permission or geological judgement. Declining advice is a
          local viewing preference.
        </small>
        <button
          type="button"
          className="secondary-button"
          onClick={() => onToggleDecline(!declinedInView)}
        >
          {declinedInView ? "Show model advice" : "Decline advice in view"}
        </button>
      </div>
    </section>
  );
}
