# Investigation design

Updated: 2026-10-14
Status: agreed product boundaries and proposed implementation; current behaviour is in the [API](api.md).

## Purpose and authority

Help a geologist review an unfamiliar drill hole, investigate intervals worth attention and share referenced evidence. Initial resource-evaluation support concerns understanding and review, not resource estimation or automatic geological certification.

```text
Question → agent interprets goal → current evidence + local model advice
         → agent/human chooses → scientific validation and tools
         → updated evidence/advice → book → expert decision
```

The chat agent coordinates the investigation. Reproducible scientific code ingests data, checks QA/depth alignment and calculates changes, overlap, comparisons and statistics. The local model supplies structured decision support. The geologist retains final judgement. Reuse the host's agent facilities; do not build a new multi-agent scheduler.

## Live book

Use React/TypeScript with Vite and a local Python service. SQLite owns persistent pages and event history. Versioned templates fill a working page as actual evidence arrives. Submitting a choice and note atomically records that decision, locks the page and creates its linked successor. Corrections create new pages; locked history is immutable.

SSE notifies the viewer only after committed writes. Sequence IDs, replay and authoritative snapshots recover after disconnect/reload. Reading history pauses auto-navigation; returning to the current page resumes following. Heartbeats only maintain a connection: they do not create evidence, turn pages or invoke models.

Keep synthetic fixtures visibly labelled. A workflow choice is not scientific approval. The current staged runner is separate from both model inference and real scientific analysis.

## Decision return

The existing demo saves decisions and updates the browser. The missing bridge must deliver the exact committed choice/note to the intended agent investigation, then return results to its successor page.

Persist the decision, successor and pending continuation in one transaction. Carry stable decision/run/page IDs, schema version, locked revision, successor ID, reviewed evidence references, timestamp and actual actor. Send submitted input rather than keystrokes or autosave drafts. A compact host receipt can identify the committed decision; tools retrieve authoritative context.

Use at-least-once delivery with idempotent application effects. Track pending/running/completed/failed states, bounded retries and recoverable claims when workers compete. Acknowledgement and successful investigation completion are distinct. Do not promise exactly-once external model invocation across crashes. Reject stale writes and late results targeting locked/unrelated pages. Add a general worker-to-ready transition independent of the synthetic runner, including honest partial/failed evidence.

First prove a supported round trip in Codex desktop. A generic browser SSE event, MCP tool call or context update alone does not demonstrate model continuation. Retain the standalone browser. If a native host panel is necessary, bring that container change for review before replacing the selected experience. Do not inject keystrokes, guess the foreground chat, edit undocumented settings or silently introduce a separately billed API/cloud path.

## Local decision model

The owner requires a locally installed fine-tuned model grounded in the organiser's HyLogger datasets. It must be meaningfully consulted during chat, not merely loaded or added as a decorative endorsement. The organiser supplies scientific measurements; that does not imply expert next-action labels exist. No real dataset is downloaded in this repository yet.

The existing synthetic logistic classifier is a mechanics baseline. It is fitted from scratch, lacks question/instruction/evidence inputs and is not the target fine-tuned model. No base checkpoint or inference runtime has been selected for the target.

Reserve this versioned boundary before parallel implementation:

```text
assess(question, instruction, state_revision, observed_evidence, candidates)
  → assessment_id, state_revision, model_version, origin,
    ranked_suggestions, evidence_gaps, uncertainty, limitations
```

Evidence includes bounded numerical features and referenced summaries, not references alone: coverage, valid counts, masks/gaps, source availability, sampling compatibility and already computed change/overlap where available. Unobserved values remain unknown. Candidates contain registered action types and bounded arguments. Deterministic numbers still come from scientific code.

Consult after a structured question, relevant tool result and committed human modification. Do not infer on page navigation or keepalives. Record the assessment revision/hash, model version, candidate set, advice and actual action separately. Refresh or visibly mark stale advice. The agent/human can accept, revise or decline suggestions; authorisation, prerequisites and revisions independently validate execution. No matching-top-suggestion receipt is required.

Only train output fields supported by labels. Action rankings do not automatically teach evidence-gap classification, calibrated uncertainty or causal explanations. Scores are not geological confidence. Clearly label `origin=fixture` for parallel UI/backend work; unavailable inference may allow authorised manual/deterministic work, but cannot masquerade as the trained model.

### Training and evaluation, held for owner discussion

A compact pretrained encoder/ranker with numerical features is a candidate architecture. Fine-tuning must update pretrained parameters; fitting only a frozen-embedding head is a baseline. Benchmark laptop latency, memory and install size before choosing the checkpoint/export/runtime. Ship tokenizer, preprocessing, schema/action versions, hashes and a model card with trained weights; isolate training dependencies from inference.

1. Inspect real packages and freeze independent hole/project train/validation/test groups before generating tasks, windows, paraphrases or fitted preprocessing.
2. Produce independently checked scientific results with source/method/parameter provenance. Define bounded answerable and unanswerable tasks and their evidence requirements.
3. Construct partial-observation episodes with meaningful alternative actions and human changes of direction. Separate native missingness from controlled masking.
4. Compare valid actions/short continuations against predeclared evidence criteria and costs. Allow ties. Record calculated, teacher-proposed, expert-reviewed and unresolved label origins; an LLM preference is not geological ground truth.
5. Keep future results and terminal outcomes out of pre-action inputs. Related windows, revisions and trajectories stay in one source group. Raw data and private trajectories remain ignored.
6. Compare rules, synthetic baseline, frozen encoder, fine-tuned ranker and the same agent without local advice on equal tools/tasks/budgets.

Evaluate acceptable-action ranking, invalid calls, clarification/stop choices, answer correctness, traceability, missing evidence and unnecessary tool cost. Run complete investigations using states created by actual chosen actions. Hold the question fixed while varying observed evidence, and evidence fixed while changing the question. Preserve failures and cases where advice worsens outcomes. One hole does not establish cross-hole generalisation.

Full acceptance requires actual fine-tuning and local advice at question/result/human-decision checkpoints, useful held-out/rollout results, and a live demonstration where the agent can disagree without bypassing scientific validation. Geological usefulness needs separately recorded expert feedback. Model work remains with the owner and Codex; it is not assigned to the two application implementers.

## Package and hosts

Target one Python runtime with scientific operations, book service, trained inference assets and prebuilt React assets, exposed through a thin MCP adapter and CLI. End users should not need Node, a source checkout, training libraries or a training run. Keep immutable installed assets separate from writable per-user books. The one-command product installer is a future goal, not an available release; host enablement/consent is a separate step.

Share contracts, science, model, backend and templates across hosts. Installation, transport, panel integration and message delivery use capability-based adapters. Test Codex desktop first and ChatGPT desktop separately. A local Python install does not establish ChatGPT web connectivity. Codex CLI can use the standalone book with explicit follow-up until a supported automatic route is proven. Web/cloud/tunnel distribution is deferred.

Host UI message APIs belong to supported integrated apps, not arbitrary localhost tabs. Implementation must verify current official host/SDK capabilities and record exact versions and actual continuation. Report installation, discovery, rendering, decision persistence, host acceptance, model invocation, tool result and ready-state evidence separately.

## Structure and names

Use one responsibility at every level. Prefer short familiar names; parent directories provide context. Avoid catch-all utilities/managers and empty scaffold layers.

| Boundary | Responsibility and representative short paths |
| --- | --- |
| `contracts/` | Validated shared shapes; canonical schemas under root `schemas/` |
| `pages/`, `runs/` | Lifecycle/application operations, such as `pages/decide.py` |
| `store/` | SQLite persistence; caller owns multi-write transactions |
| `events/` | Durable continuation delivery; distinct from browser SSE |
| `policy/` | Local loading/inference, such as `model.py`, `assess.py` |
| `science/` | Reproducible operations, such as `qa.py`, `overlap.py` |
| `server/`, `mcp/`, `cli/` | Thin transports calling shared application operations |
| `app/src/book/`, `templates/` | Book composition and page presentation |
| `app/src/state/`, `transport/`, `host/` | Reader state, backend access, capability messaging |

Python paths above live under `src/hylogger_bridge/`. Add them only when implemented behaviour requires extraction. Keep training developer-only. Adapters must not call one another over HTTP to reuse logic; UI must not duplicate scientific calculations. Extract existing broad files in bounded changes preserving imports, commands and books. Do not leave a module and same-named package competing for imports.
