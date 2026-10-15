// Resolve canonical v1 model assessments separately from scientific evidence, actions, and decisions.
import type { Assessment, BookSource, Page } from "./contracts";

export type AssessmentStatus = "none" | "fixture" | "model" | "stale" | "unavailable";

export type ResolvedAssessment = {
  status: AssessmentStatus;
  badgeLabel: string;
  isStale: boolean;
  declinedInView: boolean;
  assessment: Assessment | null;
  referencedEvidenceIds: string[];
  actualAction: string;
};

const STATUS_BADGES: Record<AssessmentStatus, string> = {
  none: "No assessment recorded",
  fixture: "Fixture advice (origin=fixture)",
  model: "Local decision model (origin=model)",
  stale: "Stale assessment",
  unavailable: "Assessment unavailable",
};

function describeActualAction(page: Page, bookSource: BookSource): string {
  if (page.action) {
    const actorLabel = page.action.actor.name
      ? `${page.action.actor.kind} (${page.action.actor.name})`
      : page.action.actor.kind;
    const consultLabel = page.action.assessment_id
      ? `consulted ${page.action.assessment_id}`
      : "no assessment consulted";
    return `Recorded action: ${page.action.type} by ${actorLabel} · ${consultLabel}`;
  }
  if (page.demo_running) {
    return bookSource === "live"
      ? `Worker active (${page.progress || "collecting evidence"})`
      : `Staged synthetic runner active (${page.progress || "collecting evidence"})`;
  }
  if (page.status === "locked" && page.decision) {
    return `Human workflow decision recorded: ${page.decision.choice}`;
  }
  if (page.status === "ready") {
    return bookSource === "live"
      ? `Evidence recorded (${page.outcome ?? "complete"}); awaiting human workflow choice`
      : "Deterministic synthetic evidence completed; awaiting human workflow choice";
  }
  if (page.evidence.length > 0) {
    return `Recorded ${page.evidence.length} evidence entries (latest: ${page.evidence[page.evidence.length - 1].id})`;
  }
  return "No tool or worker action recorded on this page yet";
}

export function resolveAssessment(
  page: Page,
  declinedInView = false,
  bookSource: BookSource = "synthetic_demo",
): ResolvedAssessment {
  const actualAction = describeActualAction(page, bookSource);
  const assessment: Assessment | null = page.assessment ?? null;

  if (assessment === null) {
    return {
      status: "none",
      badgeLabel: STATUS_BADGES.none,
      isStale: false,
      declinedInView,
      assessment: null,
      referencedEvidenceIds: [],
      actualAction,
    };
  }

  const isStale = assessment.status === "available" && assessment.state_revision < page.revision;

  const status: AssessmentStatus =
    assessment.status === "unavailable" ? "unavailable" : isStale ? "stale" : assessment.origin;

  const referencedEvidenceIds = Array.from(
    new Set(assessment.suggestions.flatMap((item) => item.evidence_ids)),
  );

  return {
    status,
    badgeLabel: STATUS_BADGES[status],
    isStale,
    declinedInView,
    assessment,
    referencedEvidenceIds,
    actualAction,
  };
}
