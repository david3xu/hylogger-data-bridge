// Validate canonical v1 contracts against schemas/v1.json and shared semantic rules.
import v1Schema from "../../../schemas/v1.json";

export const BUILTIN_SYNTHETIC_SOURCE = "Built-in synthetic fixture v1";

export type DecisionChoice = "accept" | "modify" | "reject";
export type EvidenceKind = "observation" | "calculation" | "limitation";
export type EvidenceOrigin = "actual" | "synthetic" | "unspecified";
export type EvidenceState = "complete" | "partial" | "failed";
export type PageOutcome = "complete" | "partial" | "failed";
export type PageStatus = "draft" | "ready" | "locked";
export type BookSource = "synthetic_demo" | "live";

export type DeliveryState =
  | "saved"
  | "pending_delivery"
  | "accepted"
  | "working"
  | "failed"
  | "needs_input"
  | "ready";

export type ErrorCode =
  | "invalid_request"
  | "not_found"
  | "stale_revision"
  | "page_locked"
  | "not_ready"
  | "unrelated_page"
  | "request_reuse"
  | "unavailable"
  | "delivery_failed"
  | "worker_failed"
  | "claim_expired";

export type ContractErrorObject = {
  error: string;
  code: ErrorCode;
  retryable: boolean;
};

export type Actor = {
  kind: "human" | "agent" | "system";
  name?: string;
};

export type Worker = {
  kind: "agent" | "system";
  name?: string;
};

export type DecisionActor = {
  kind: "human" | "unknown";
  name?: string;
};

export type Evidence = {
  id: string;
  label: string;
  value: string;
  source: string;
  kind: EvidenceKind;
  origin?: EvidenceOrigin;
  state?: EvidenceState;
};

export type DecisionRequest = {
  choice: DecisionChoice;
  note: string;
  expected_revision: number;
  request_id: string;
};

export type RecordedDecision = {
  id?: string;
  page_id?: string;
  choice: DecisionChoice;
  note: string;
  request_id?: string;
  locked_revision?: number;
  successor_id?: string;
  evidence_ids?: string[];
  actor?: DecisionActor;
  recorded_at: string;
};

export type ContinuationState = "pending" | "running" | "completed" | "failed";

export type Continuation = {
  id: string;
  decision_id: string;
  page_id: string;
  successor_id: string;
  locked_revision: number;
  state: ContinuationState;
  attempts: number;
  max_attempts: number;
  claimed_by: string | null;
  lease_expires_at: string | null;
  acknowledged_at: string | null;
  last_error: ContractErrorObject | null;
  created_at: string;
  updated_at: string;
};

export type Handoff = {
  contract_version: 1;
  continuation_id: string;
  decision_id: string;
  run_id: string;
  page_id: string;
  successor_id: string;
  locked_revision: number;
  attempt: number;
  choice: DecisionChoice;
  note: string;
  evidence_ids: string[];
  actor: {
    kind: "human";
    name?: string;
  };
  decided_at: string;
};

export type Action = {
  type: string;
  assessment_id: string | null;
  actor: Worker;
  recorded_at: string;
};

export type AssessmentOrigin = "fixture" | "model";
export type AssessmentAvailability = "available" | "unavailable";

export type Suggestion = {
  candidate_id: string;
  rank: number;
  rationale: string;
  evidence_ids: string[];
};

export type Assessment = {
  contract_version: 1;
  id: string;
  page_id: string;
  state_revision: number;
  model_version: string;
  origin: AssessmentOrigin;
  status: AssessmentAvailability;
  request_hash: string;
  suggestions: Suggestion[];
  evidence_gaps: string[];
  uncertainty: string | null;
  limitations: string[];
  created_at: string;
};

export type AssessmentRequest = {
  contract_version: 1;
  page_id: string;
  state_revision: number;
  question: string;
  instruction: string;
  evidence: Array<{
    evidence_id: string;
    kind: EvidenceKind;
    state: EvidenceState;
    features: Record<string, number | null>;
  }>;
  candidates: Array<{
    id: string;
    action_type: string;
    arguments: Record<string, string | number | boolean | null>;
  }>;
};

export type Page = {
  id: string;
  number: number;
  parent_id: string | null;
  template: string;
  template_version: 1;
  title: string;
  question: string;
  status: PageStatus;
  revision: number;
  summary: string;
  progress: string;
  evidence: Evidence[];
  outcome?: PageOutcome | null;
  errors?: ContractErrorObject[];
  decision: RecordedDecision | null;
  action?: Action | null;
  assessment?: Assessment | null;
  created_at: string;
  updated_at: string;
  scientific_review: "unreviewed";
  demo_running?: boolean;
};

export type BookEventType =
  | "page_created"
  | "demo_started"
  | "demo_interrupted"
  | "evidence_added"
  | "page_ready"
  | "decision_recorded"
  | "continuation_changed"
  | "assessment_recorded";

export type BookEvent = {
  sequence: number;
  type: string;
  page_id: string;
  at: string;
  detail: string;
};

export type Book = {
  contract_version?: 1;
  run_id: string;
  source: BookSource;
  current_page_id: string;
  sequence: number;
  pages: Page[];
  continuations?: Continuation[];
  events: BookEvent[];
};

type SchemaNode = Record<string, unknown>;
type SchemaRoot = { $defs: Record<string, SchemaNode> } & SchemaNode;

const SCHEMA_ROOT = v1Schema as unknown as SchemaRoot;

const NOTES = new Set(["$schema", "$id", "$defs", "$comment", "title", "description"]);
const RULES = new Set([
  "$ref",
  "type",
  "enum",
  "const",
  "required",
  "properties",
  "additionalProperties",
  "maxProperties",
  "items",
  "minItems",
  "maxItems",
  "uniqueItems",
  "contains",
  "minLength",
  "maxLength",
  "pattern",
  "minimum",
  "maximum",
  "if",
  "then",
  "anyOf",
  "allOf",
]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function matchesSchemaType(kind: string, value: unknown): boolean {
  switch (kind) {
    case "object":
      return isObject(value);
    case "array":
      return Array.isArray(value);
    case "string":
      return typeof value === "string";
    case "boolean":
      return typeof value === "boolean";
    case "null":
      return value === null;
    case "integer":
      return typeof value === "number" && Number.isSafeInteger(value);
    case "number":
      return typeof value === "number" && Number.isFinite(value);
    default:
      throw new Error(`Unsupported schema type ${kind}`);
  }
}

function samePrimitive(left: unknown, right: unknown): boolean {
  return typeof left === typeof right && left === right;
}

function resolveRef(ref: string, root: SchemaRoot): SchemaNode {
  const prefix = "#/$defs/";
  const name = ref.slice(prefix.length);
  if (!ref.startsWith(prefix) || !(name in root.$defs)) {
    throw new Error(`Unknown contract reference ${ref}`);
  }
  return root.$defs[name];
}

function canonicalSerialize(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalSerialize).join(",")}]`;
  }
  if (isObject(value)) {
    const entries = Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalSerialize(value[key])}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}

export function walkSchema(
  rule: SchemaNode,
  value: unknown,
  root: SchemaRoot = SCHEMA_ROOT,
  path = "$",
): string[] {
  for (const key of Object.keys(rule)) {
    if (!NOTES.has(key) && !RULES.has(key)) {
      throw new Error(`Unsupported schema keyword ${key}`);
    }
  }
  const out: string[] = [];
  if (typeof rule.$ref === "string") {
    out.push(...walkSchema(resolveRef(rule.$ref, root), value, root, path));
  }
  if ("type" in rule) {
    const kinds = Array.isArray(rule.type) ? (rule.type as string[]) : [String(rule.type)];
    if (!kinds.some((kind) => matchesSchemaType(kind, value))) {
      return [...out, `${path}: expected ${kinds.join("/")}`];
    }
  }
  if (Array.isArray(rule.enum) && !rule.enum.some((item) => samePrimitive(value, item))) {
    out.push(`${path}: not an allowed value`);
  }
  if ("const" in rule && !samePrimitive(value, rule.const)) {
    out.push(`${path}: must be ${JSON.stringify(rule.const)}`);
  }

  if (isObject(value)) {
    const required = Array.isArray(rule.required) ? (rule.required as string[]) : [];
    for (const req of required) {
      if (!(req in value)) {
        out.push(`${path}: missing ${req}`);
      }
    }
    const properties = isObject(rule.properties)
      ? (rule.properties as Record<string, SchemaNode>)
      : {};
    const extra = rule.additionalProperties ?? true;
    if (typeof rule.maxProperties === "number" && Object.keys(value).length > rule.maxProperties) {
      out.push(`${path}: too many properties`);
    }
    for (const [name, item] of Object.entries(value)) {
      if (name in properties) {
        out.push(...walkSchema(properties[name], item, root, `${path}.${name}`));
      } else if (extra === false) {
        out.push(`${path}: unexpected ${name}`);
      } else if (isObject(extra)) {
        out.push(...walkSchema(extra, item, root, `${path}.${name}`));
      }
    }
  } else if (Array.isArray(value)) {
    if (typeof rule.minItems === "number" && value.length < rule.minItems) {
      out.push(`${path}: too few items`);
    }
    if (typeof rule.maxItems === "number" && value.length > rule.maxItems) {
      out.push(`${path}: too many items`);
    }
    if (rule.uniqueItems === true) {
      const serialized = value.map(canonicalSerialize);
      if (new Set(serialized).size !== serialized.length) {
        out.push(`${path}: items must be unique`);
      }
    }
    if (isObject(rule.items)) {
      value.forEach((item, index) => {
        out.push(...walkSchema(rule.items as SchemaNode, item, root, `${path}[${index}]`));
      });
    }
    if (isObject(rule.contains)) {
      const hasMatch = value.some(
        (item) => walkSchema(rule.contains as SchemaNode, item, root, path).length === 0,
      );
      if (!hasMatch) {
        out.push(`${path}: no item matches`);
      }
    }
  } else if (typeof value === "string") {
    if (typeof rule.minLength === "number" && value.length < rule.minLength) {
      out.push(`${path}: too short`);
    }
    if (typeof rule.maxLength === "number" && value.length > rule.maxLength) {
      out.push(`${path}: too long`);
    }
    if (typeof rule.pattern === "string") {
      const regex = new RegExp(rule.pattern);
      if (value.endsWith("\n") || !regex.test(value)) {
        out.push(`${path}: does not match the required format`);
      }
    }
  } else if (typeof value === "number" && Number.isFinite(value)) {
    if (typeof rule.minimum === "number" && value < rule.minimum) {
      out.push(`${path}: below the minimum`);
    }
    if (typeof rule.maximum === "number" && value > rule.maximum) {
      out.push(`${path}: above the maximum`);
    }
  }

  if (Array.isArray(rule.allOf)) {
    for (const subRule of rule.allOf as SchemaNode[]) {
      out.push(...walkSchema(subRule, value, root, path));
    }
  }
  if (Array.isArray(rule.anyOf)) {
    const tries = (rule.anyOf as SchemaNode[]).map((subRule) =>
      walkSchema(subRule, value, root, path),
    );
    if (tries.every((res) => res.length > 0)) {
      out.push(`${path}: matches none of the allowed shapes (${tries[0][0]})`);
    }
  }
  if (isObject(rule.if) && isObject(rule.then)) {
    if (walkSchema(rule.if, value, root, path).length === 0) {
      out.push(...walkSchema(rule.then, value, root, path));
    }
  }

  return out;
}

export function problems(name: string, value: unknown): string[] {
  return walkSchema(resolveRef(`#/$defs/${name}`, SCHEMA_ROOT), value, SCHEMA_ROOT);
}

export function validateContract(name: string, value: unknown): void {
  const found = problems(name, value);
  if (found.length > 0) {
    throw new Error(found.slice(0, 5).join("; "));
  }
}

export function isId(value: unknown): value is string {
  return problems("Id", value).length === 0;
}

export function isTime(value: unknown): value is string {
  return problems("Time", value).length === 0;
}

export function isHash(value: unknown): value is string {
  return problems("Hash", value).length === 0;
}

export function isToken(value: unknown): value is string {
  return problems("Token", value).length === 0;
}

export function isContractError(value: unknown): value is ContractErrorObject {
  return problems("Error", value).length === 0;
}

export function isActor(value: unknown): value is Actor {
  return problems("Actor", value).length === 0;
}

export function isWorker(value: unknown): value is Worker {
  return problems("Worker", value).length === 0;
}

export function isEvidence(value: unknown): value is Evidence {
  return problems("Evidence", value).length === 0;
}

export function isDecisionRequest(value: unknown): value is DecisionRequest {
  return problems("DecisionRequest", value).length === 0;
}

export function isDecision(value: unknown): value is RecordedDecision {
  return problems("Decision", value).length === 0;
}

export function isContinuation(value: unknown): value is Continuation {
  return problems("Continuation", value).length === 0;
}

export function isHandoff(value: unknown): value is Handoff {
  return problems("Handoff", value).length === 0;
}

export function isAction(value: unknown): value is Action {
  return problems("Action", value).length === 0;
}

export function isAssessment(value: unknown): value is Assessment {
  return problems("Assessment", value).length === 0;
}

export function isAssessmentRequest(value: unknown): value is AssessmentRequest {
  return problems("AssessmentRequest", value).length === 0;
}

export function isCompletion(value: unknown): boolean {
  return problems("Completion", value).length === 0;
}

export function isPage(value: unknown): value is Page {
  return problems("Page", value).length === 0;
}

export function isBookSchemaValid(value: unknown): value is Book {
  return problems("Book", value).length === 0;
}

export function checkAdvice(request: unknown, advice: unknown, expectedRequestHash?: string): void {
  validateContract("AssessmentRequest", request);
  validateContract("Assessment", advice);
  const req = request as AssessmentRequest;
  const adv = advice as Assessment;

  const offered = req.candidates.map((item) => item.id);
  const shown = new Set(req.evidence.map((item) => item.evidence_id));
  const picks = adv.suggestions.map((item) => item.candidate_id);
  const ranks = adv.suggestions.map((item) => item.rank);
  const cited = adv.suggestions.flatMap((item) => item.evidence_ids);

  if (new Set(offered).size !== offered.length) {
    throw new Error("request repeats a candidate");
  }
  if (adv.page_id !== req.page_id) {
    throw new Error("advice belongs to another page");
  }
  if (adv.state_revision !== req.state_revision) {
    throw new Error("advice answers another revision");
  }
  if (expectedRequestHash !== undefined && adv.request_hash !== expectedRequestHash) {
    throw new Error("advice answers another request");
  }
  if (picks.some((pick) => !offered.includes(pick))) {
    throw new Error("advice names a candidate the request lacks");
  }
  if (new Set(picks).size !== picks.length) {
    throw new Error("advice repeats a candidate");
  }
  if (new Set(ranks).size !== ranks.length) {
    throw new Error("advice repeats a rank");
  }
  if (cited.some((ref) => !shown.has(ref))) {
    throw new Error("advice cites evidence the request lacks");
  }
}

export function checkBook(value: unknown): Book {
  const invalid = new Error("The local service returned an unsupported book snapshot.");
  if (!isBookSchemaValid(value)) {
    throw invalid;
  }
  const pages = new Map<string, Page>();
  for (const page of value.pages) {
    if (pages.has(page.id)) throw invalid;
    pages.set(page.id, page);
  }

  const roots = value.pages.filter((page) => page.parent_id === null);
  if (roots.length !== 1) throw invalid;

  for (const page of value.pages) {
    const heldIds = page.evidence.map((item) => item.id);
    if (new Set(heldIds).size !== heldIds.length) throw invalid;
    if (page.assessment) {
      if (page.assessment.page_id !== page.id) throw invalid;
      const picks = page.assessment.suggestions.map((s) => s.candidate_id);
      const ranks = page.assessment.suggestions.map((s) => s.rank);
      if (new Set(picks).size !== picks.length || new Set(ranks).size !== ranks.length) {
        throw invalid;
      }
      const heldSet = new Set(heldIds);
      for (const s of page.assessment.suggestions) {
        if (s.evidence_ids.some((id) => !heldSet.has(id))) throw invalid;
      }
    }
    if (page.parent_id === null) {
      if (page.number !== 1) throw invalid;
    } else {
      const parent = pages.get(page.parent_id);
      if (!parent || !parent.decision) throw invalid;
      if (parent.decision.successor_id !== page.id) throw invalid;
      if (page.number !== parent.number + 1) throw invalid;
    }
  }

  if (!pages.has(value.current_page_id)) throw invalid;
  const unlockedIds = value.pages.filter((page) => page.status !== "locked").map((page) => page.id);
  if (unlockedIds.length !== 1 || unlockedIds[0] !== value.current_page_id) {
    throw invalid;
  }

  for (const page of value.pages) {
    const decision = page.decision;
    if (!decision) continue;
    const heldSet = new Set(page.evidence.map((item) => item.id));
    const child = decision.successor_id ? pages.get(decision.successor_id) : undefined;
    if (
      decision.page_id !== page.id ||
      decision.locked_revision !== page.revision ||
      !decision.evidence_ids ||
      decision.evidence_ids.some((id) => !heldSet.has(id)) ||
      child?.parent_id !== page.id
    ) {
      throw invalid;
    }
  }

  const continuations = value.continuations ?? [];
  const stepByPage = new Map<string, Continuation>();
  const stepIds = new Set<string>();
  for (const step of continuations) {
    if (stepByPage.has(step.page_id) || stepIds.has(step.id) || !pages.has(step.page_id)) {
      throw invalid;
    }
    stepByPage.set(step.page_id, step);
    stepIds.add(step.id);
  }

  for (const page of value.pages) {
    const decision = page.decision;
    const step = stepByPage.get(page.id);
    const dispatched = decision !== null && decision.actor?.kind === "human";
    if (dispatched && !step) throw invalid;
    if (!dispatched && step) throw invalid;
    if (!step || !decision) continue;
    if (
      step.decision_id !== decision.id ||
      step.successor_id !== decision.successor_id ||
      step.locked_revision !== decision.locked_revision ||
      step.attempts > step.max_attempts
    ) {
      throw invalid;
    }
  }

  const sequences = value.events.map((event) => event.sequence);
  for (let i = 0; i < sequences.length; i++) {
    if (i > 0 && sequences[i] <= sequences[i - 1]) throw invalid;
  }
  if (sequences.length > 0 && sequences[sequences.length - 1] > value.sequence) {
    throw invalid;
  }

  return value;
}

function isLegacySnapshotCandidate(value: Record<string, unknown>): boolean {
  if ("contract_version" in value || "continuations" in value) return false;
  if (!Array.isArray(value.pages)) return false;
  return value.pages.every(
    (page) => isObject(page) && !("outcome" in page) && !("errors" in page) && !("action" in page),
  );
}

function isLegacyDecisionActor(value: unknown): value is DecisionActor {
  if (!isObject(value)) return false;
  const keys = Object.keys(value);
  if (keys.some((k) => k !== "kind" && k !== "name")) return false;
  if (value.kind !== "human" && value.kind !== "unknown") return false;
  if (value.name !== undefined) {
    if (typeof value.name !== "string" || value.name.length < 1 || value.name.length > 200) {
      return false;
    }
  }
  return true;
}

function decodeLegacyBook(value: Record<string, unknown>): Book {
  const invalid = new Error("The local service returned an unsupported book snapshot.");
  const allowedKeys = new Set([
    "run_id",
    "source",
    "current_page_id",
    "sequence",
    "pages",
    "events",
  ]);
  if (
    Object.keys(value).length !== allowedKeys.size ||
    !Object.keys(value).every((k) => allowedKeys.has(k)) ||
    !isId(value.run_id) ||
    (value.source !== "synthetic_demo" && value.source !== "live") ||
    !isId(value.current_page_id) ||
    typeof value.sequence !== "number" ||
    !Number.isSafeInteger(value.sequence) ||
    value.sequence < 0 ||
    !Array.isArray(value.pages) ||
    value.pages.length === 0 ||
    !Array.isArray(value.events)
  ) {
    throw invalid;
  }

  const pages: Page[] = value.pages.map((rawPage) => {
    if (
      !isObject(rawPage) ||
      !isId(rawPage.id) ||
      typeof rawPage.number !== "number" ||
      !Number.isSafeInteger(rawPage.number) ||
      rawPage.number < 1 ||
      !(rawPage.parent_id === null || isId(rawPage.parent_id)) ||
      typeof rawPage.template !== "string" ||
      rawPage.template_version !== 1 ||
      typeof rawPage.title !== "string" ||
      typeof rawPage.question !== "string" ||
      !["draft", "ready", "locked"].includes(String(rawPage.status)) ||
      typeof rawPage.revision !== "number" ||
      !Number.isSafeInteger(rawPage.revision) ||
      rawPage.revision < 0 ||
      typeof rawPage.summary !== "string" ||
      typeof rawPage.progress !== "string" ||
      !Array.isArray(rawPage.evidence) ||
      typeof rawPage.created_at !== "string" ||
      typeof rawPage.updated_at !== "string" ||
      rawPage.scientific_review !== "unreviewed" ||
      !(rawPage.demo_running === undefined || typeof rawPage.demo_running === "boolean")
    ) {
      throw invalid;
    }

    const evidence: Evidence[] = rawPage.evidence.map((ev) => {
      if (
        !isObject(ev) ||
        !isId(ev.id) ||
        typeof ev.label !== "string" ||
        ev.label.length < 1 ||
        ev.label.length > 4000 ||
        typeof ev.value !== "string" ||
        ev.value.length < 1 ||
        ev.value.length > 4000 ||
        typeof ev.source !== "string" ||
        ev.source.length < 1 ||
        ev.source.length > 4000 ||
        !["observation", "calculation", "limitation"].includes(String(ev.kind))
      ) {
        throw invalid;
      }

      let origin: EvidenceOrigin;
      if (ev.origin !== undefined) {
        if (ev.origin !== "actual" && ev.origin !== "synthetic" && ev.origin !== "unspecified") {
          throw invalid;
        }
        origin = ev.origin;
      } else {
        origin = ev.source === BUILTIN_SYNTHETIC_SOURCE ? "synthetic" : "unspecified";
      }

      let state: EvidenceState;
      if (ev.state !== undefined) {
        if (ev.state !== "complete" && ev.state !== "partial" && ev.state !== "failed") {
          throw invalid;
        }
        state = ev.state;
      } else {
        state = "complete";
      }

      return {
        id: ev.id,
        label: ev.label,
        value: ev.value,
        source: ev.source,
        kind: ev.kind as EvidenceKind,
        origin,
        state,
      };
    });

    let decision: RecordedDecision | null = null;
    if (rawPage.decision !== null && rawPage.decision !== undefined) {
      if (
        !isObject(rawPage.decision) ||
        !["accept", "modify", "reject"].includes(String(rawPage.decision.choice)) ||
        typeof rawPage.decision.note !== "string" ||
        rawPage.decision.note.length > 4000 ||
        !isTime(rawPage.decision.recorded_at)
      ) {
        throw invalid;
      }

      let actor: DecisionActor = { kind: "unknown" };
      if (rawPage.decision.actor !== undefined) {
        if (!isLegacyDecisionActor(rawPage.decision.actor)) {
          throw invalid;
        }
        actor = rawPage.decision.actor;
      }

      let requestId: string | undefined;
      if (rawPage.decision.request_id !== undefined) {
        if (
          typeof rawPage.decision.request_id !== "string" ||
          rawPage.decision.request_id.length < 1 ||
          rawPage.decision.request_id.length > 200
        ) {
          throw invalid;
        }
        requestId = rawPage.decision.request_id;
      }

      let decisionId: string | undefined;
      if (rawPage.decision.id !== undefined) {
        if (!isId(rawPage.decision.id)) {
          throw invalid;
        }
        decisionId = rawPage.decision.id;
      }

      let successorId: string | undefined;
      if (rawPage.decision.successor_id !== undefined) {
        if (!isId(rawPage.decision.successor_id)) {
          throw invalid;
        }
        successorId = rawPage.decision.successor_id;
      }

      let lockedRevision: number | undefined;
      if (rawPage.decision.locked_revision !== undefined) {
        if (
          typeof rawPage.decision.locked_revision !== "number" ||
          !Number.isSafeInteger(rawPage.decision.locked_revision) ||
          rawPage.decision.locked_revision < 0
        ) {
          throw invalid;
        }
        lockedRevision = rawPage.decision.locked_revision;
      }

      let evidenceIds: string[] | undefined;
      if (rawPage.decision.evidence_ids !== undefined) {
        if (
          !Array.isArray(rawPage.decision.evidence_ids) ||
          !rawPage.decision.evidence_ids.every(isId)
        ) {
          throw invalid;
        }
        evidenceIds = rawPage.decision.evidence_ids;
      }

      decision = {
        choice: rawPage.decision.choice as DecisionChoice,
        note: rawPage.decision.note,
        recorded_at: rawPage.decision.recorded_at,
        actor,
        ...(decisionId !== undefined ? { id: decisionId } : {}),
        ...(requestId !== undefined ? { request_id: requestId } : {}),
        ...(successorId !== undefined ? { successor_id: successorId } : {}),
        ...(lockedRevision !== undefined ? { locked_revision: lockedRevision } : {}),
        ...(evidenceIds !== undefined ? { evidence_ids: evidenceIds } : {}),
      };
    }

    if (rawPage.status === "locked" && decision === null) {
      throw invalid;
    }

    let assessment: Assessment | null = null;
    if (rawPage.assessment !== undefined && rawPage.assessment !== null) {
      if (!isAssessment(rawPage.assessment)) {
        throw invalid;
      }
      assessment = rawPage.assessment;
    }

    return {
      id: rawPage.id,
      number: rawPage.number,
      parent_id: rawPage.parent_id as string | null,
      template: rawPage.template,
      template_version: 1,
      title: rawPage.title,
      question: rawPage.question,
      status: rawPage.status as PageStatus,
      revision: rawPage.revision,
      summary: rawPage.summary,
      progress: rawPage.progress,
      evidence,
      outcome: rawPage.status === "draft" ? null : "complete",
      errors: [],
      decision,
      action: null,
      assessment,
      created_at: rawPage.created_at,
      updated_at: rawPage.updated_at,
      scientific_review: "unreviewed",
      demo_running: Boolean(rawPage.demo_running),
    };
  });

  if (!pages.some((page) => page.id === value.current_page_id)) {
    throw invalid;
  }

  const events: BookEvent[] = value.events.map((ev) => {
    if (
      !isObject(ev) ||
      typeof ev.sequence !== "number" ||
      !Number.isSafeInteger(ev.sequence) ||
      ev.sequence < 1 ||
      typeof ev.type !== "string" ||
      !isId(ev.page_id) ||
      typeof ev.at !== "string" ||
      typeof ev.detail !== "string"
    ) {
      throw invalid;
    }
    return {
      sequence: ev.sequence,
      type: ev.type,
      page_id: ev.page_id,
      at: ev.at,
      detail: ev.detail,
    };
  });

  return {
    run_id: value.run_id,
    source: value.source as BookSource,
    current_page_id: value.current_page_id,
    sequence: value.sequence,
    pages,
    continuations: [],
    events,
  };
}

export function decodeBook(value: unknown): Book {
  const invalid = new Error("The local service returned an unsupported book snapshot.");
  if (!isObject(value)) {
    throw invalid;
  }
  if (isLegacySnapshotCandidate(value)) {
    return decodeLegacyBook(value);
  }
  return checkBook(value);
}
