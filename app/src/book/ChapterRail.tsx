// Render the persistent chapter rail for browsing current and historical investigation pages.
import type { HostCapability } from "../host/bridge";
import type { Book, Page } from "../state/contracts";

type ChapterRailProps = {
  book: Book | null;
  selectedPageId: string | undefined;
  hostCapability: HostCapability;
  onSelectPage: (id: string) => void;
};

function chapterStatusText(item: Page): string {
  if (item.status === "locked") return "Sealed · decision recorded";
  if (item.status === "ready") return "Ready for your decision";
  if (item.demo_running) return "Working · collecting evidence";
  return "Working page";
}

export function ChapterRail({
  book,
  selectedPageId,
  hostCapability,
  onSelectPage,
}: ChapterRailProps) {
  const isLive = book?.source === "live";

  return (
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
            className={`chapter ${item.id === selectedPageId ? "active" : ""}`}
            aria-current={item.id === selectedPageId ? "page" : undefined}
            onClick={() => onSelectPage(item.id)}
          >
            <span className="chapter-number">{String(item.number).padStart(2, "0")}</span>
            <span>
              <strong>{item.title}</strong>
              <small>{chapterStatusText(item)}</small>
            </span>
            <span className="chapter-indicator" aria-hidden="true">
              {item.status === "locked" ? "✓" : "·"}
            </span>
          </button>
        ))}
      </nav>
      <div className="rail-foot">
        {isLive ? (
          <>
            <span className="demo-tag">Live investigation</span>
            <p>
              Local SQLite workflow.
              <br />
              Provenance recorded per entry.
            </p>
          </>
        ) : (
          <>
            <span className="demo-tag">Synthetic demonstration</span>
            <p>
              A local live workflow.
              <br />
              No real drill-hole data.
            </p>
          </>
        )}
        <small className="host-tag" title={hostCapability.detail}>
          {hostCapability.automaticDispatchAvailable
            ? `Host bridge: ${hostCapability.hostName}`
            : "Mode: Standalone · explicit chat follow-up"}
        </small>
      </div>
    </aside>
  );
}
