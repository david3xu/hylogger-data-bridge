# Investigation design

Updated: 2026-10-15
Status: agreed product boundaries and proposed implementation; current behaviour is in the [API](api.md).

## Purpose and authority

Help a geologist review an unfamiliar drill hole, investigate intervals worth attention and share referenced evidence. Initial resource-evaluation support concerns understanding and review, not resource estimation or automatic geological certification.

```text
Question → agent interprets goal → current evidence + local model advice
         → agent/human chooses → scientific validation and tools
         → updated evidence/advice → book → expert decision
```

The chat agent coordinates the investigation. Reproducible scientific code ingests data, checks QA/depth alignment and calculates changes, overlap, comparisons and statistics. The local model supplies structured decision support. The geologist retains final judgement. Reuse the host's agent facilities; do not build a new multi-agent scheduler.

## MVP scope: resource-evaluation evidence review

Focus on one application within Data Adoption: helping an expert understand and review drill-hole evidence supporting resource evaluation. The broader theme's application examples are not this project's feature checklist. The first version does not promise coverage of every industry use case.

The target user task is: review an unfamiliar drill hole, identify intervals deserving attention, compare available evidence and record a traceable review decision. The initial real demonstration is one hole, one bounded investigation and one auditable expert review cycle:

> Review this hole for spectral-change intervals that overlap available assays. Compare selected intervals, show data limitations and prepare an evidence package for geological review.

| Area | First-version boundary |
| --- | --- |
| Resource-evaluation support | Package/QA review, transparent change candidates, interval comparisons, available assay overlap and referenced evidence |
| Alteration-related evidence | Spectral/mineral changes may inform the investigation; a complete alteration-mapping product is outside the MVP |
| Resource estimation and reporting | Tonnage/grade estimation, block modelling, reserves and formal resource reporting are outside the MVP |
| Operational applications | Grade-control decisions and ore–waste classification are outside the MVP |
| Other applications | Geometallurgy and environmental assessment are outside the MVP |

The fine-tuned local advisory model remains a core requirement within this bounded workflow; narrowing the application does not remove it. The agent interprets questions, scientific tools calculate evidence, the model advises on useful follow-ups and the book records actual expert decisions. A flagged interval is a review candidate, not proof of ore or mineralisation.

Judge product value on a real case: whether an expert can find and verify relevant evidence with fewer manual steps, clear limitations and source provenance. Where feasible, compare task time, manual steps, evidence completeness and expert usability against the existing manual workflow. Define success criteria before evaluation and record actual reviewer feedback; do not claim improvement from a synthetic UI demo. Separately evaluate whether model advice improves investigation outcomes as specified in [training](training.md#5-evaluate-added-value).

A one-hole product demonstration is distinct from the independent source groups needed to assess model generalisation. Propose a feature only when it helps complete this review workflow; expanding to another application needs an explicit scope decision. Current synthetic demos remain mechanics evidence, not proof of immediate industry value.

## TSG ingestion with pytsg

Use GSWA's [pytsg](https://github.com/Geological-Survey-of-Western-Australia/pytsg) as the TSG-package reader behind our scientific adapter. Its documented `pytsg.read_tsg(package_path)` interface exposes package data, including spectral arrays and wavelengths. pytsg is pinned in `training/science.txt`; the R1 pilot read and checked real organiser packages through it (see [training](training.md#r1-real-data-pilot)).

```text
Local TSG package → pytsg → validated internal data contract
    → reproducible scientific operations
        → referenced evidence and plots for the book
        → observed features for model training and live assessment
```

Keep the dependency boundary in a focused proposed module, `src/hylogger_bridge/science/tsg.py`. It loads inspected packages, maps their available fields and reports missing products with provenance. Validate dimensions, row/depth correspondence, units, processing levels and mask semantics before downstream calculations. Do not invent universal mineral/scalar fields or assume all packages contain all spectral regions. Preserve the meaning of existing TSG processing; reading interpreted outputs does not independently validate them or rerun mineral unmixing.

Separate QA, interval comparison, change detection and depth overlap into their own scientific operations. Associated assay tables need a separate reader and verified hole/depth/unit linkage; the pytsg adapter does not establish that linkage. The frontend, chat adapter and model inference must not import pytsg directly. Bounded application tools invoke the scientific layer and return referenced results, not entire raw arrays to the chat.

Use the same adapter, calculation methods and feature definitions for offline training preparation and live investigations. pytsg provides access to scientific data; it does not supply next-action supervision or the fine-tuned decision model. Keep raw packages, large arrays and generated records outside Git. Inspect dependency compatibility and pin the reviewed version through the assigned Python configuration owner when integration is authorised.

The next bounded scientific slice is [S1 in the task plan](tasks.md#s1--inspect-and-adapt-one-tsg-package). It is separate from the initial frontend/backend assignments; recording it does not dispatch implementation or download data.

## Live book

Use React/TypeScript with Vite and a local Python service. SQLite owns persistent pages and event history. Versioned templates fill a working page as actual evidence arrives. Submitting a choice and note atomically records that decision, locks the page and creates its linked successor. Corrections create new pages; locked history is immutable.

SSE notifies the viewer only after committed writes. Sequence IDs, replay and authoritative snapshots recover after disconnect/reload. Reading history pauses auto-navigation; returning to the current page resumes following. Transport keepalives only maintain a connection: they do not create evidence, turn pages or invoke models.

Keep synthetic fixtures visibly labelled. A workflow choice is not scientific approval. The current staged runner is separate from both model inference and real scientific analysis.

## Decision return

The existing demo saves decisions and updates the browser. The missing bridge must deliver the exact committed choice/note to the intended agent investigation, then return results to its successor page.

Owner clarification (15 October 2026): automatic updates in both directions remain the intended product behaviour. A lightweight watcher may check for newly committed decisions; unchanged checks must not invoke a model. A new pending decision must reach the bound host investigation through a supported adapter, which starts or queues actual agent work and returns evidence to the book. SSE keepalives, polling a queue and starting a model turn are distinct operations. Manual chat follow-up is a fallback and does not pass automatic-loop acceptance. This host wakeup is still unimplemented; no automatic mode may be advertised until the same-session round trip is observed.

Persist the decision, successor and pending continuation in one transaction. Carry stable decision/run/page IDs, schema version, locked revision, successor ID, reviewed evidence references, timestamp and actual actor. Send submitted input rather than keystrokes or autosave drafts. A compact host receipt can identify the committed decision; tools retrieve authoritative context.

Use at-least-once delivery with idempotent application effects. Track pending/running/completed/failed states, bounded retries and recoverable claims when workers compete. Acknowledgement and successful investigation completion are distinct. Do not promise exactly-once external model invocation across crashes. Reject stale writes and late results targeting locked/unrelated pages. Add a general worker-to-ready transition independent of the synthetic runner, including honest partial/failed evidence.

First prove a supported round trip in Codex desktop. A generic browser SSE event, MCP tool call or context update alone does not demonstrate model continuation. Retain the standalone browser. If a native host panel is necessary, bring that container change for review before replacing the selected experience. Do not inject keystrokes, guess the foreground chat, edit undocumented settings or silently introduce a separately billed API/cloud path.

Official capabilities need host-specific verification: [Codex App Server](https://learn.chatgpt.com/docs/app-server) exposes explicit turn-start operations for clients, but this does not establish that a plugin can attach to an existing desktop conversation. [MCP Events](https://developers.openai.com/plugins/build/mcp-events) documents webhook-triggered Work Cloud/dot surfaces; it does not prove the local Codex route. Do not replace that missing proof with a recurring model call labelled a heartbeat.

## Local decision model

The owner requires a locally installed fine-tuned model grounded in the organiser's HyLogger datasets. It must be meaningfully consulted during chat, not merely loaded or added as a decorative endorsement. The organiser supplies scientific measurements; that does not imply expert next-action labels exist. The R1 pilot downloaded 19 frozen NVCL WA packages (ignored by Git) and trained on teaching-rule labels; its model matches the majority baseline.

The existing synthetic logistic classifier is a mechanics baseline. It is fitted from scratch, lacks question/instruction/evidence inputs and is not the target fine-tuned model. The owner selected Qwen3.5-4B with LoRA and a decision head for the first experiment on 2026-10-15. A synthetic local run and offline base/adapter reload have been verified; measured evidence and remaining real-data limits are in [project instructions](../../CLAUDE.md#local-qwen-demonstration-evidence).

Reserve this versioned boundary before parallel implementation:

```text
assess(question, instruction, state_revision, observed_evidence, candidates)
  → assessment_id, state_revision, model_version, origin,
    ranked_suggestions, evidence_gaps, uncertainty, limitations
```

Evidence includes bounded numerical features and referenced summaries, not references alone: coverage, valid counts, masks/gaps, source availability, sampling compatibility and already computed change/overlap where available. Unobserved values remain unknown. Candidates contain registered action types and bounded arguments. Deterministic numbers still come from scientific code.

Consult after a structured question, relevant tool result and committed human modification. Do not infer on page navigation or keepalives. Record the assessment revision/hash, model version, candidate set, advice and actual action separately. Refresh or visibly mark stale advice. The agent/human can accept, revise or decline suggestions; authorisation, prerequisites and revisions independently validate execution. No matching-top-suggestion receipt is required.

Only train output fields supported by labels. Action rankings do not automatically teach evidence-gap classification, calibrated uncertainty or causal explanations. Scores are not geological confidence. Clearly label `origin=fixture` for parallel UI/backend work; unavailable inference may allow authorised manual/deterministic work, but cannot masquerade as the trained model.

### Training and evaluation

The data-to-model process is maintained in [local model training](training.md): real-package inspection, grounded partial-observation records, explicit label origins, advisory-model fine-tuning, independent source-group evaluation and local export. The owner authorised the synthetic Qwen3.5-4B experiment, then resumed real-data work and assigned Claude the bounded [R1 delivery](tasks.md#r1--claude-real-data-model). That permits necessary pilot-package preparation and training; expert geological validation remains distinct. Additional compute purchases and full-collection downloads remain outside scope.

The full model feature requires demonstrated real-data fine-tuning, meaningful advisory integration and evaluated investigation outcomes. Claude's completed backend handoff stays separate from the new R1 model branch; Gemini's application assignment remains separate from model/data work.

## Package and hosts

Target one Python runtime with scientific operations, book service, trained inference assets and prebuilt React assets, exposed through a thin MCP adapter and CLI. End users should not need Node, a source checkout, training libraries or a training run. Keep immutable installed assets separate from writable per-user books. The one-command product installer is a future goal, not an available release; host enablement/consent is a separate step.

The target experience is unchanged: install once, connect a supported data folder, chat normally, watch the book, decide and continue. Version one ships a documented fallback instead (see the [README quickstart](../../README.md#real-data-quickstart)): explicit `training.live demo` and `continue` commands beside the browser book. The fallback is not the target experience and does not demonstrate tool selection during chat or automatic continuation.

Share contracts, science, model, backend and templates across hosts. Installation, transport, panel integration and message delivery use capability-based adapters. Test Codex desktop first and ChatGPT desktop separately. A local Python install does not establish ChatGPT web connectivity. Codex CLI can use the standalone book with explicit follow-up until a supported automatic route is proven. Web/cloud/tunnel distribution is deferred.

Host UI message APIs belong to supported integrated apps, not arbitrary localhost tabs. Implementation must verify current official host/SDK capabilities and record exact versions and actual continuation. Report installation, discovery, rendering, decision persistence, host acceptance, model invocation, tool result and ready-state evidence separately.

## Structure and names

Owner decision recorded on 2026-10-15: keep the current repository structure. Refine data/output organisation when the deferred real-data preparation work resumes; do not reorganise the repository now or create a separate decision-model repository. Keep developer training under root `training/` and runtime model inference under `src/hylogger_bridge/advice/`.

At that later stage, separate raw scientific packages from prepared decision records and group generated models, metrics and logs by training run. Raw data, generated records, model weights and run outputs remain ignored. This is a later organisation task, not an instruction to move existing files or create empty folders now. See the [real-data deferral](training.md#owner-decision-real-data-training-deferred).

Use one responsibility at every level. Prefer short familiar names; parent directories provide context. Avoid catch-all utilities/managers and empty scaffold layers.

| Boundary | Responsibility and representative short paths |
| --- | --- |
| `contracts/` | Validated shared shapes; canonical schemas under root `schemas/` |
| `pages/`, `runs/` | Lifecycle/application operations, such as `pages/decide.py` |
| `store/` | SQLite persistence; caller owns multi-write transactions |
| `events/` | Durable continuation delivery; distinct from browser SSE |
| `advice/` | Local model loading/inference; preserve the existing baseline `policy.py` import |
| `science/` | Reproducible operations, such as `qa.py`, `overlap.py` |
| `server/`, `mcp/`, `cli/` | Thin transports calling shared application operations |
| `app/src/book/`, `templates/` | Book composition and page presentation |
| `app/src/state/`, `transport/`, `host/` | Reader state, backend access, capability messaging |

Python paths above live under `src/hylogger_bridge/`. Add them only when implemented behaviour requires extraction. Keep training developer-only. Adapters must not call one another over HTTP to reuse logic; UI must not duplicate scientific calculations. Extract existing broad files in bounded changes preserving imports, commands and books. Do not leave a module and same-named package competing for imports.
