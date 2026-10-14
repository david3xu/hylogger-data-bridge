// Render a live research book whose historical pages preserve actual user choices.
import { useEffect, useState } from "react";
import type { DecisionChoice, Evidence, Page } from "./book";
import { useBook } from "./useBook";

const choiceLabels: Record<DecisionChoice, string> = {
  accept: "Continue with this evidence",
  modify: "Change the investigation",
  reject: "Set this candidate aside",
};

function IntervalFigure() {
  return (
    <figure className="interval-figure">
      <svg viewBox="0 0 600 150" role="img" aria-labelledby="interval-title interval-description">
        <title id="interval-title">Synthetic depth interval overlap</title>
        <desc id="interval-description">
          A synthetic candidate extends from 214 to 220 metres. A synthetic assay record covers 215
          to 218 metres. They overlap for 3 metres.
        </desc>
        <g className="figure-grid">
          <line x1="120" y1="28" x2="120" y2="113" />
          <line x1="190" y1="28" x2="190" y2="113" />
          <line x1="400" y1="28" x2="400" y2="113" />
          <line x1="540" y1="28" x2="540" y2="113" />
        </g>
        <text x="0" y="58">
          Candidate
        </text>
        <text x="0" y="99">
          Assay record
        </text>
        <rect x="120" y="39" width="420" height="26" rx="3" className="candidate-bar" />
        <rect x="190" y="80" width="210" height="26" rx="3" className="assay-bar" />
        <g className="depth-labels">
          <text x="120" y="137">
            214 m
          </text>
          <text x="190" y="137">
            215
          </text>
          <text x="400" y="137">
            218
          </text>
          <text x="540" y="137">
            220 m
          </text>
        </g>
      </svg>
      <figcaption>
        Illustrative geometry · 3 m overlap / 6 m candidate = 50%. All values are synthetic.
      </figcaption>
    </figure>
  );
}

function EvidenceRow({ item, index }: { item: Evidence; index: number }) {
  return (
    <article className={`evidence-row evidence-${item.kind}`}>
      <span className="evidence-number">{String(index + 1).padStart(2, "0")}</span>
      <div>
        <span className="eyebrow">{item.kind}</span>
        <h3>{item.label}</h3>
        <p>{item.value}</p>
        <small>{item.source}</small>
      </div>
    </article>
  );
}

function ReviewForm({
  page,
  busy,
  onDecide,
}: {
  page: Page;
  busy: boolean;
  onDecide: (choice: DecisionChoice, note: string) => Promise<boolean>;
}) {
  const [choice, setChoice] = useState<DecisionChoice>("accept");
  const [note, setNote] = useState("");
  return (
    <form
      className="review-box"
      onSubmit={(event) => {
        event.preventDefault();
        void onDecide(choice, note);
      }}
    >
      <div className="section-heading">
        <span className="eyebrow">Your next step</span>
        <span className="ready-dot">Ready for a workflow decision</span>
      </div>
      <h2>Where should this investigation go?</h2>
      <p className="quiet">
        Your choice seals this page and opens the next one. Geological findings remain unreviewed.
      </p>
      <fieldset disabled={busy}>
        <legend className="visually-hidden">Choose the next direction</legend>
        <div className="decision-choices">
          {(["accept", "modify", "reject"] as const).map((item) => (
            <label className={choice === item ? "choice selected" : "choice"} key={item}>
              <input
                type="radio"
                name={`choice-${page.id}`}
                value={item}
                checked={choice === item}
                onChange={() => setChoice(item)}
              />
              <span>{choiceLabels[item]}</span>
            </label>
          ))}
        </div>
        <label className="note-label" htmlFor="decision-note">
          Investigation note <span>(optional)</span>
        </label>
        <textarea
          id="decision-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={2000}
          rows={3}
          placeholder="What should the next page examine?"
        />
        <div className="decision-footer">
          <small>This records your workflow choice, not geological approval.</small>
          <button type="submit" className="primary-button">
            {busy ? "Saving decision…" : "Record decision & turn page"}
            <span aria-hidden="true">↗</span>
          </button>
        </div>
      </fieldset>
    </form>
  );
}

export function App() {
  const viewer = useBook();
  const { book, error, connection, busy } = viewer;
  const page = book?.pages.find((item) => item.id === viewer.selectedId);
  const pageId = page?.id;
  useEffect(() => {
    if (pageId) window.scrollTo({ top: 0 });
  }, [pageId]);
  const liveLabel = {
    connecting: "Connecting",
    live: "Live updates",
    reconnecting: "Reconnecting",
    offline: "Service unavailable",
  }[connection];
  return (
    <div className="book-shell">
      <aside className="chapter-rail">
        <a className="wordmark" href="#book">
          <span className="mark" aria-hidden="true">
            F
          </span>
          <span>
            fieldnotes<span className="wordmark-sub">HyLogger investigation book</span>
          </span>
        </a>
        <div className="rail-intro">
          <span className="eyebrow">Investigation 001</span>
          <h1>
            A question.
            <br />A trail of evidence.
          </h1>
          <p>
            Each decision becomes a page.
            <br />
            The record stays with you.
          </p>
        </div>
        <nav aria-label="Investigation pages">
          <div className="rail-label">
            <span>Contents</span>
            <span>{book ? String(book.pages.length).padStart(2, "0") : "—"}</span>
          </div>
          {book?.pages.map((item) => (
            <button
              type="button"
              key={item.id}
              className={`chapter ${item.id === page?.id ? "active" : ""}`}
              aria-current={item.id === page?.id ? "page" : undefined}
              onClick={() => viewer.select(item.id)}
            >
              <span className="chapter-number">{String(item.number).padStart(2, "0")}</span>
              <span>
                <strong>{item.title}</strong>
                <small>
                  {item.status === "locked"
                    ? "Sealed · decision recorded"
                    : item.status === "ready"
                      ? "Ready for your decision"
                      : "Working page"}
                </small>
              </span>
              <span className="chapter-indicator" aria-hidden="true">
                {item.status === "locked" ? "✓" : "·"}
              </span>
            </button>
          ))}
        </nav>
        <div className="rail-foot">
          <span className="demo-tag">Synthetic demonstration</span>
          <p>
            A local live workflow.
            <br />
            No real drill-hole data.
          </p>
        </div>
      </aside>
      <main id="book" className="book-main">
        <header className="topbar">
          <span>
            FIELD JOURNAL <span className="topbar-divider">/</span> RESOURCE EVALUATION
          </span>
          <output className={`connection ${connection}`}>
            <span className="connection-dot" />
            {liveLabel}
          </output>
        </header>
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button type="button" onClick={viewer.retry}>
              Retry connection
            </button>
          </div>
        )}
        {!book && (
          <section className="loading-page">
            <span className="eyebrow">Opening your investigation</span>
            <h2>{error ? "The local book is unavailable." : "Gathering the pages…"}</h2>
            <p>
              {error
                ? "Start the local book service, then retry the connection."
                : "Your saved evidence and decisions will appear here."}
            </p>
          </section>
        )}
        {page && (
          <>
            <div className="reading-controls">
              <span>
                {viewer.following
                  ? "Following the latest page"
                  : "Reading history · live navigation paused"}
              </span>
              {!viewer.following && (
                <button type="button" onClick={viewer.follow}>
                  Return to latest page <span aria-hidden="true">→</span>
                </button>
              )}
              <span className="sequence-label">Saved event {book?.sequence}</span>
            </div>
            <article className="paper-page" key={page.id}>
              <div className="page-heading">
                <span className="eyebrow">
                  {page.template === "investigation"
                    ? "01 / Investigation"
                    : "02 / Candidate evidence"}
                </span>
                <span className={`page-status ${page.status}`}>
                  {page.status === "locked"
                    ? "Sealed record"
                    : page.status === "ready"
                      ? "Ready for review"
                      : "Working draft"}
                </span>
              </div>
              <div className="page-title">
                <h2>{page.title}</h2>
                <span className="folio">
                  <span className="visually-hidden">Page </span>
                  {String(page.number).padStart(2, "0")}
                </span>
              </div>
              <div className="question">
                <span className="eyebrow">The question</span>
                <p>{page.question}</p>
              </div>
              <p className="page-summary">
                {page.summary ||
                  "This page will collect the evidence needed to explore the question."}
              </p>
              <output className="progress-line">
                <span className={page.status === "draft" ? "working-pulse" : "progress-tick"}>
                  {page.status === "draft" ? "◌" : "✓"}
                </span>
                <span>{page.progress || "Waiting for the investigation to begin."}</span>
                <span className="revision">revision {page.revision}</span>
              </output>
              {page.evidence.length > 0 ? (
                <section className="evidence-section" aria-label="Evidence">
                  <div className="section-heading">
                    <span className="eyebrow">The evidence so far</span>
                    <span className="quiet small">
                      {page.evidence.length} entries · synthetic sources
                    </span>
                  </div>
                  {page.evidence.map((item, index) => (
                    <EvidenceRow item={item} index={index} key={item.id} />
                  ))}
                  {page.evidence.some(
                    (item) =>
                      item.id === "synthetic-overlap" &&
                      item.source === "Built-in synthetic fixture v1",
                  ) && <IntervalFigure />}
                </section>
              ) : (
                <div className="empty-evidence">
                  <span className="empty-mark" aria-hidden="true">
                    ⌁
                  </span>
                  <div>
                    <h3>A place for the evidence.</h3>
                    <p>Start the synthetic case to see this page fill as results arrive.</p>
                  </div>
                </div>
              )}
              {page.status === "draft" && (
                <div className="start-row">
                  <button
                    className="primary-button"
                    type="button"
                    disabled={busy || page.demo_running}
                    onClick={() => {
                      void viewer.start(page);
                    }}
                  >
                    {page.demo_running
                      ? "Collecting synthetic evidence…"
                      : busy
                        ? "Starting…"
                        : page.evidence.length
                          ? "Resume synthetic case"
                          : "Start synthetic case"}
                    <span aria-hidden="true">→</span>
                  </button>
                  <p>
                    A staged example; it does not run scientific analysis or the trained selector.
                  </p>
                </div>
              )}
              {page.status === "ready" && (
                <ReviewForm
                  key={`${page.id}-${page.revision}`}
                  page={page}
                  busy={busy}
                  onDecide={(choice, note) => viewer.decide(page, choice, note)}
                />
              )}
              {page.decision && (
                <section className="sealed-decision">
                  <span className="eyebrow">Recorded workflow decision</span>
                  <h2>{choiceLabels[page.decision.choice]}</h2>
                  <p>{page.decision.note || "No additional note was recorded."}</p>
                  <small>
                    Page sealed {new Date(page.decision.recorded_at).toLocaleString()} · Read-only
                    history
                  </small>
                </section>
              )}
              <footer className="page-footer">
                <span>FIELDNOTES / LOCAL DEMO</span>
                <span>
                  Scientific review: <strong>unreviewed</strong>
                </span>
                <span>{String(page.number).padStart(2, "0")}</span>
              </footer>
            </article>
            <p className="outside-note">
              Evidence is saved locally. A sealed page preserves a workflow decision; it does not
              validate a geological conclusion.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
