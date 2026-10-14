// Resolve canonical v1 model assessments separately from scientific evidence, actions, and decisions.
import type { Assessment, BookSource, Page } from "./contracts";

export type AssessmentStatus = "fixture" | "model" | "stale" | "unavailable";

export type ResolvedAssessment = {
  status: AssessmentStatus;
  badgeLabel: string;
  isStale: boolean;
  declinedInView: boolean;
  assessment: Assessment;
  referencedEvidenceIds: string[];
  actualAction: string;
};

const STATUS_BADGES: Record<AssessmentStatus, string> = {
  fixture: "Fixture advice (origin=fixture)",
  model: "Local decision model (origin=model)",
  stale: "Stale assessment",
  unavailable: "Assessment unavailable",
};

const FIXTURE_HASH = "77b6337144604a1234d30e55128e50649bc1f7517fa79a4d3b23ee764201044e";

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

function buildBoundaryFixture(page: Page, bookSource: BookSource): Assessment {
  if (
    bookSource === "live" ||
    (page.number > 1 && page.evidence.length === 0) ||
    page.outcome === "failed"
  ) {
    return {
      contract_version: 1,
      id: `assess-unavail-${page.id}`,
      page_id: page.id,
      state_revision: page.revision,
      model_version: "fixture-v1",
      origin: "fixture",
      status: "unavailable",
      request_hash: FIXTURE_HASH,
      suggestions: [],
      evidence_gaps: [],
      uncertainty: null,
      limitations: ["No local model is installed; manual or deterministic work remains possible."],
      created_at: page.updated_at,
    };
  }

  if (page.status === "draft" && page.revision >= 2) {
    const firstEvidence = page.evidence.slice(0, 1).map((item) => item.id);
    return {
      contract_version: 1,
      id: `assess-stale-${page.id}`,
      page_id: page.id,
      state_revision: 1,
      model_version: "fixture-v1",
      origin: "fixture",
      status: "available",
      request_hash: FIXTURE_HASH,
      suggestions: [
        {
          candidate_id: "cand-overlap",
          rank: 1,
          rationale: "Fixture ordering for interface development; no model produced this.",
          evidence_ids: firstEvidence,
        },
        {
          candidate_id: "cand-qa",
          rank: 2,
          rationale: "Fixture ordering for interface development; no model produced this.",
          evidence_ids: [],
        },
      ],
      evidence_gaps: [`Evaluated at revision 1; page is now at revision ${page.revision}.`],
      uncertainty: null,
      limitations: [
        "Labelled fixture: no trained model was consulted.",
        "A ranking never authorises an action.",
      ],
      created_at: page.created_at,
    };
  }

  const citedIds = page.evidence.slice(0, 1).map((item) => item.id);
  return {
    contract_version: 1,
    id: `assess-${page.id}`,
    page_id: page.id,
    state_revision: page.revision,
    model_version: "fixture-v1",
    origin: "fixture",
    status: "available",
    request_hash: FIXTURE_HASH,
    suggestions: [
      {
        candidate_id: "cand-overlap",
        rank: 1,
        rationale: "Fixture ordering for interface development; no model produced this.",
        evidence_ids: citedIds,
      },
      {
        candidate_id: "cand-qa",
        rank: 2,
        rationale: "Fixture ordering for interface development; no model produced this.",
        evidence_ids: [],
      },
    ],
    evidence_gaps: ["Fixture does not assess gaps."],
    uncertainty: null,
    limitations: [
      "Labelled fixture: no trained model was consulted.",
      "A ranking never authorises an action.",
    ],
    created_at: page.updated_at,
  };
}

export function resolveAssessment(
  page: Page,
  declinedInView = false,
  bookSource: BookSource = "synthetic_demo",
): ResolvedAssessment {
  const assessment: Assessment = page.assessment ?? buildBoundaryFixture(page, bookSource);

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
    actualAction: describeActualAction(page, bookSource),
  };
}
