// Render scientific evidence items with explicit provenance and state, separate from advice.
import type { BookSource, Evidence } from "../state/contracts";
import { IntervalFigure } from "../templates/IntervalFigure";

function originLabel(origin: Evidence["origin"]): string {
  switch (origin) {
    case "actual":
      return "Provenance: actual";
    case "synthetic":
      return "Provenance: synthetic";
    case "unspecified":
      return "Provenance: unspecified";
    default:
      return "Provenance: unspecified";
  }
}

function EvidenceRow({ item, index }: { item: Evidence; index: number }) {
  const state = item.state ?? "complete";
  return (
    <article
      className={`evidence-row evidence-${item.kind} state-${state}`}
      data-evidence-id={item.id}
      data-evidence-origin={item.origin ?? "unspecified"}
    >
      <span className="evidence-number">{String(index + 1).padStart(2, "0")}</span>
      <div>
        <span className="eyebrow">
          {item.kind} · {originLabel(item.origin)}
          {state !== "complete" ? ` · state=${state}` : ""}
        </span>
        <h3>{item.label}</h3>
        <p>{item.value}</p>
        <small>Source: {item.source}</small>
      </div>
    </article>
  );
}

export function EvidenceList({
  evidence,
  bookSource = "synthetic_demo",
}: {
  evidence: Evidence[];
  bookSource?: BookSource;
}) {
  if (evidence.length === 0) {
    return (
      <div className="empty-evidence">
        <span className="empty-mark" aria-hidden="true">
          ⌁
        </span>
        <div>
          <h3>A place for the evidence.</h3>
          <p>
            {bookSource === "live"
              ? "Evidence will appear here as investigation results are recorded."
              : "Start the synthetic case to see this page fill as results arrive."}
          </p>
        </div>
      </div>
    );
  }

  const hasSyntheticOverlap = evidence.some(
    (item) =>
      item.id === "synthetic-overlap" &&
      (item.origin === "synthetic" || item.source === "Built-in synthetic fixture v1"),
  );

  return (
    <section className="evidence-section" aria-label="Scientific evidence">
      <div className="section-heading">
        <span className="eyebrow">
          Scientific evidence (observations, calculations &amp; limits)
        </span>
        <span className="quiet small">
          {evidence.length} entries ·{" "}
          {bookSource === "live" ? "live book provenance" : "synthetic demo provenance"}
        </span>
      </div>
      {evidence.map((item, index) => (
        <EvidenceRow item={item} index={index} key={item.id} />
      ))}
      {hasSyntheticOverlap && <IntervalFigure />}
    </section>
  );
}
