// Present versioned page framing, lineage links, and scientific review boundaries.
import type { ReactNode } from "react";
import type { Page } from "../state/contracts";

type PageTemplateProps = {
  page: Page;
  parentPage?: Page;
  successorPage?: Page;
  onSelectPage: (id: string) => void;
  children?: ReactNode;
};

export function templateEyebrow(page: Page): string {
  const label =
    page.template === "investigation" ? "01 / Investigation" : "02 / Candidate evidence";
  return `${label} · template v${page.template_version}`;
}

export function statusBadgeText(status: Page["status"]): string {
  switch (status) {
    case "locked":
      return "Sealed record";
    case "ready":
      return "Ready for review";
    case "draft":
      return "Working draft";
  }
}

export function PageTemplate({
  page,
  parentPage,
  successorPage,
  onSelectPage,
  children,
}: PageTemplateProps) {
  return (
    <article className="paper-page" key={page.id}>
      <div className="page-heading">
        <span className="eyebrow">{templateEyebrow(page)}</span>
        <span className={`page-status ${page.status}`}>{statusBadgeText(page.status)}</span>
      </div>

      {(parentPage || successorPage) && (
        <nav className="lineage-bar" aria-label="Page lineage">
          {parentPage ? (
            <button
              type="button"
              className="lineage-link"
              onClick={() => onSelectPage(parentPage.id)}
            >
              ← Continues from Page {String(parentPage.number).padStart(2, "0")} ({parentPage.title}
              )
            </button>
          ) : (
            <span className="lineage-origin">Initial page of investigation</span>
          )}
          {successorPage && (
            <button
              type="button"
              className="lineage-link successor"
              onClick={() => onSelectPage(successorPage.id)}
            >
              Continued on Page {String(successorPage.number).padStart(2, "0")} (
              {successorPage.title}) →
            </button>
          )}
        </nav>
      )}

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
        {page.summary || "This page will collect the evidence needed to explore the question."}
      </p>

      <output className="progress-line">
        <span className={page.status === "draft" ? "working-pulse" : "progress-tick"}>
          {page.status === "draft" ? "◌" : "✓"}
        </span>
        <span>{page.progress || "Waiting for the investigation to begin."}</span>
        <span className="revision">revision {page.revision}</span>
      </output>

      {children}

      <footer className="page-footer">
        <span>FIELDNOTES / LOCAL DEMO</span>
        <span>
          Scientific review: <strong>{page.scientific_review}</strong>
        </span>
        <span>{String(page.number).padStart(2, "0")}</span>
      </footer>
    </article>
  );
}
