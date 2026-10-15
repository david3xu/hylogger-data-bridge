// Compose the live investigation book from focused state, template, and book modules.
import { useEffect } from "react";
import { AssessmentPanel } from "./book/AssessmentPanel";
import { ChapterRail } from "./book/ChapterRail";
import { DecisionForm, SealedDecision } from "./book/DecisionForm";
import { DeliveryStatusBar } from "./book/DeliveryStatusBar";
import { EvidenceList } from "./book/EvidenceList";
import { ReturnStatus } from "./book/ReturnStatus";
import { resolveAssessment } from "./state/assessment";
import { resolveDelivery } from "./state/delivery";
import { findParentPage, findSuccessorPage, isAssessmentDeclined } from "./state/reader";
import { PageTemplate } from "./templates/PageTemplate";
import { useBook } from "./useBook";

const CONNECTION_LABELS = {
  connecting: "Connecting",
  live: "Live updates",
  reconnecting: "Reconnecting",
  offline: "Service unavailable",
} as const;

export function App() {
  const viewer = useBook();
  const { book, error, connection, busy, hostCapability } = viewer;
  const page = book?.pages.find((item) => item.id === viewer.selectedId);
  const pageId = page?.id;

  useEffect(() => {
    if (pageId) window.scrollTo({ top: 0 });
  }, [pageId]);

  const draft = page ? viewer.getPageDraft(page) : undefined;
  const hostDelivery = page ? viewer.getPageHostDelivery(page) : undefined;
  const delivery = page ? resolveDelivery(book, page, draft, hostDelivery) : undefined;
  const adviceDeclined = page ? isAssessmentDeclined(viewer, page.id) : false;
  const assessment = page ? resolveAssessment(page, adviceDeclined, book?.source) : undefined;
  const parentPage = page ? findParentPage(book, page) : undefined;
  const successorPage = page ? findSuccessorPage(book, page) : undefined;
  const isLiveBook = book?.source === "live";

  return (
    <div className="book-shell">
      <ChapterRail
        book={book}
        selectedPageId={page?.id}
        hostCapability={hostCapability}
        onSelectPage={viewer.select}
      />
      <main id="book" className="book-main">
        <header className="topbar">
          <span>
            FIELD JOURNAL <span className="topbar-divider">/</span> RESOURCE EVALUATION
          </span>
          <output className={`connection ${connection}`}>
            <span className="connection-dot" />
            {CONNECTION_LABELS[connection]}
          </output>
        </header>

        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <div className="error-actions">
              {page && draft?.status === "failed" && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    void viewer.decide(page, draft.choice, draft.note);
                  }}
                >
                  Retry decision
                </button>
              )}
              {delivery?.retryableHostDelivery && delivery.hostDeliveryPageId && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    if (delivery.hostDeliveryPageId) {
                      void viewer.retryHostDelivery(delivery.hostDeliveryPageId);
                    }
                  }}
                >
                  Retry host delivery
                </button>
              )}
              <button type="button" onClick={viewer.retry}>
                Retry connection
              </button>
            </div>
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

        {page && delivery && assessment && draft && (
          <>
            <div className="reading-controls">
              <span>
                {viewer.following
                  ? "Following the latest page"
                  : "Reading history · live navigation paused"}
              </span>
              {viewer.following ? (
                <button type="button" onClick={viewer.pause}>
                  Pause following
                </button>
              ) : (
                <button type="button" onClick={viewer.follow}>
                  Return to latest page <span aria-hidden="true">→</span>
                </button>
              )}
              <span className="sequence-label">Saved event {book?.sequence}</span>
            </div>

            <PageTemplate
              page={page}
              parentPage={parentPage}
              successorPage={successorPage}
              onSelectPage={viewer.select}
            >
              <DeliveryStatusBar
                delivery={delivery}
                busy={busy}
                onRetryHostDelivery={(targetPageId) => {
                  void viewer.retryHostDelivery(targetPageId);
                }}
              />

              <ReturnStatus
                sequence={book?.sequence || 0}
                pending={Boolean(book?.continuations?.some((item) => item.state === "pending"))}
              />
              <EvidenceList evidence={page.evidence} bookSource={book?.source} />

              <AssessmentPanel
                resolved={assessment}
                pageRevision={page.revision}
                onToggleDecline={(declined) => viewer.setAdviceDeclined(page.id, declined)}
              />

              {page.status === "draft" &&
                (isLiveBook ? (
                  <div className="start-row">
                    <p>
                      Live investigation draft · awaiting worker or scientific tool evidence for
                      this page.
                    </p>
                  </div>
                ) : (
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
                ))}

              {page.status === "ready" && (
                <DecisionForm
                  page={page}
                  draft={draft}
                  busy={busy}
                  adviceDeclinedInView={adviceDeclined}
                  draftSaveStatus={viewer.drafts[page.id] ? viewer.draftSaveStatus : null}
                  onChangeDraft={(choice, note) => viewer.updateDecisionDraft(page, choice, note)}
                  onSubmitDecision={(choice, note) => viewer.decide(page, choice, note)}
                />
              )}

              {page.decision && (
                <SealedDecision
                  page={page}
                  successorPage={successorPage}
                  onSelectPage={viewer.select}
                />
              )}
            </PageTemplate>

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
