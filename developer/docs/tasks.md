# Application implementation tasks

Updated: 2026-10-15
Status: owner-mediated briefs. The owner explicitly assigned R1 real-data model work to Claude on 2026-10-15; the copyable handoff carries that assignment into Claude Desktop.

## Scope gate

All slices serve the [resource-evaluation evidence-review MVP](design.md#mvp-scope-resource-evaluation-evidence-review). The first real case is a bounded one-hole investigation with referenced evidence and a recorded expert review cycle, not a platform implementing every Data Adoption application. Preserve the local fine-tuned advisory-model boundary. UI/transport acceptance, model quality, scientific correctness and expert usefulness require separate evidence; a synthetic demonstration cannot certify all four. Application expansion needs an explicit scope decision.

## Ownership and branches

Current handover: the owner has returned technical coordination, architecture and independent review to Codex. Implementation collaborators receive self-contained briefs and return handoffs through the owner's manual copy/paste relay. A brief or PR comment is not automatic dispatch. The [current handover and release audit](submission.md#technical-ownership-handover) supersede historical role assignments while preserving concurrent branch/path boundaries.

| Owner | Branch | Initial scope |
| --- | --- | --- |
| Claude Sonnet | `codex/claude-backend` | Shared contracts, backend lifecycle and supported host-return feasibility |
| Gemini Argon | `codex/gemini-frontend` | Live book, assessment display and human decision interaction |
| Claude | `codex/claude-real-model` | R1: real organiser-data preparation, bounded scientific adapter, model fine-tuning and verification |
| Owner + Codex | Architecture and independent review | Model scope, scientific/label/evaluation review and branch integration |

Each worker must use a separate worktree or clone. Do not switch the shared checkout's branch while another worker runs. After fetching the prepared branches, separate worktrees can be created from the repository root:

```sh
git fetch origin
git worktree add ../hylogger-claude codex/claude-backend
git worktree add ../hylogger-gemini codex/gemini-frontend
```

If only remote branches exist, create the corresponding local tracking branch in the new worktree. Inspect existing worktrees first and reuse an appropriate one instead of overwriting it. Never reset, clean or force-push another worker's work.

Read [design](design.md), [implemented API](api.md), [project instructions](../../CLAUDE.md) and [GitHub workflow](github.md). Agree the smallest versioned page/evidence/assessment contract before consumer changes diverge. Claude owns canonical schemas; Gemini owns frontend consumers and jointly expected boundary fixtures. Label fixture advice visibly; do not wait for trained weights or implement model training.

## Claude: backend brief

Work on `codex/claude-backend` in your isolated checkout. Keep the existing synthetic demo usable and preserve current SQLite books and CLI/import compatibility.

1. Freeze the minimal shared contracts for pages, evidence, decisions, continuation, tool results and model assessment. Include revisions, stable IDs, provenance, errors and fixture origin. Use one canonical schema source and matching Python/TypeScript acceptance/rejection fixtures. Return the contract change for review before broad integration.
2. Extract application operations, storage and HTTP/SSE concerns only where needed. Commit decision, page lock, successor and pending continuation in one transaction. Add durable pending/running/completed/failed delivery with bounded retries and idempotent results. Notify the browser after commit.
3. Add a general worker-to-ready operation with partial/failed evidence, independent of the staged runner. Reject stale/locked/unrelated result writes and preserve exact committed notes. Reserve a replaceable local assessment provider. Advice does not authorise execution; valid actions may differ from its top suggestion.
4. In a bounded feasibility spike, prove a supported committed-decision → actual Codex model turn → result → successor route. Record host/SDK versions and the exact message/session mechanism. A mocked consumer, SSE event or context update is not proof of continuation. If a native panel is required, return the container choice for owner review. Do not replace the browser or add a paid API/cloud/tunnel workaround.
5. Expose approved operations through thin MCP/HTTP adapters when the host route is proven. Tool writes must not fabricate human decisions or scientific approvals.

Own Python backend/application/storage/transport modules, canonical schemas and corresponding tests. Coordinate cross-language contract changes with Gemini. Claude owns necessary Python dependency/lock changes during this first backend slice; Gemini owns only frontend dependencies. Do not edit model/training modules or real-data preparation. Scientific adapter implementation and package installers are later separately assigned work, not part of this initial brief.

Pass: duplicate decisions/deliveries create one successor and idempotent effects; crashes at delivery boundaries recover; concurrent/stale results preserve history; a real worker can finish a page without demo stages. Report host continuation as blocked/unverified if it cannot be demonstrated and continue independent lifecycle work. Return changed paths, module responsibilities, migration effects, actual checks and limitations.

## Gemini: frontend brief

Work on `codex/gemini-frontend` in your isolated checkout. Build on the existing React/TypeScript/Vite book; preserve its side-by-side reading experience.

1. Split broad components, reader state, backend networking, host capability messaging and templates into short focused modules as behaviour requires. Use Claude's agreed schemas; do not create a second competing API design.
2. Preserve live evidence, locked history, linked successors, reconnect/reload recovery and paused following while reading history. Use sequenced events and authoritative snapshots rather than treating event text as a separate database.
3. Show the exact choice and typed note through submission/retry. Distinguish saved, pending delivery, accepted by agent, working, failed/needs input and ready based on real backend states. Preserve request IDs across retries; do not manufacture success or submit duplicate decisions.
4. Present assessment advice separately from observations, calculated results, actual actions and human decisions. Show model version, evidence references, limitations and visible fixture/unavailable/stale status. Users and agents may disagree with advice. No local training or invented confidence values.
5. Keep standalone view functional. Add a host adapter only for the proven capability agreed with Claude. An ordinary localhost page cannot assume host messaging APIs exist. If the actual route needs a different container, return it for architecture review before replacing the chosen browser mode.

Own `app/` and its package/lock files and frontend tests. Coordinate schema requests through Claude. Do not edit Python storage, training, runtime packaging, root CI or shared release files concurrently. Do not implement an installer, model fitting, data preparation, cloud service or custom scheduler under this brief.

Pass: demonstrate streaming, a real submitted choice/note, persisted immutable history, successor navigation, retries/reconnect, visible delivery failure and clearly labelled advice fixtures. A heartbeat must not trigger content or model work. Return changed paths, responsibilities, exact checks, visible demo evidence and remaining limits.

## S1 — Inspect and adapt one TSG package

Status: Claude owns the minimum inspection/adapter/comparison work needed for R1 under the owner's new real-data assignment. The completed backend handoff and Gemini's frontend brief remain separate. The owner and Codex retain architecture and independent review.

Follow the [pytsg boundary](design.md#tsg-ingestion-with-pytsg) and [data handling](../../data/README.md). The first deliverable is a package inventory and verified mapping, before broad parser or analysis work:

1. Select one manageable real organiser package and record source, retrieval time, licence, hashes and file inventory. Inspect available spectra, wavelengths, depths, masks, scalars/mineral outputs and processing levels; explicitly record missing or ambiguous fields.
2. Verify pytsg compatibility in an isolated environment. Exercise its documented reader on that package. Return actual shapes, field meanings, row/depth correspondence and any loading failures. Coordinate dependency/lock changes with the assigned Python configuration owner; do not install speculative imaging options by default.
3. Implement only the needed adapter under proposed `science/tsg.py` after mapping review. Keep file reading separate from QA and calculations. Return a validated internal contract with stable sample references, source/method metadata, units and explicit unknowns. Preserve original values and processing provenance.
4. Add the smallest independently checked QA and interval-comparison operation justified by the inspected data. Use explicit depth boundaries, mask handling, valid counts and method/parameter versions. Verify a small known selection against an independent calculation; fixture tests must cover missing products, dimensional mismatch, empty selections and invalid measurements where relevant.
5. Demonstrate one real interval result suitable for the book and one bounded observed-feature record suitable for training preparation. These are scientific results, not expert-approved conclusions or next-action labels. Share the same feature definitions with live inference preparation.

Pass: a reproducible one-hole load and independently verified comparison, with provenance, limitations and an inventory of unsupported fields. No fabricated fallback values or synthetic-to-real relabelling. Keep real data out of Git/hosted CI; ordinary tests use small clearly labelled fixtures. Do not infer cross-hole generalisation from this pilot.

Later scientific slices may add change detection, a separate assay reader and verified interval overlap. Do not claim that pytsg alone provides those analyses, assay linkage or model supervision. Schema changes require coordination with Claude; frontend presentation uses Gemini's existing evidence contract. Return changed paths, module responsibilities, exact checks and unresolved scientific questions.

## R1 — Claude real-data model

Owner assignment: resume the previously deferred real-data work. Deliver one bounded real-data Qwen3.5-4B training run and a locally runnable, hash-verified artifact, using actual organiser measurements. Writing scripts or regenerating the synthetic smoke dataset does not complete this task.

Branch: `codex/claude-real-model`, prepared remotely from completed backend handoff `00be2338cda40083dc3d52b1a71bc6b2edccdcd6`. Use only Claude's clean isolated checkout; preserve `codex/claude-delivery` and PR #3 as the completed backend handoff. Open a new draft PR against `codex/claude-delivery`. The existing main-ancestry issue remains with the Git-capable integrator; do not repeat file-copy integration.

Claude owns `training/`, the minimum `src/hylogger_bridge/science/` adapter/calculations and shared feature builder, corresponding tests and necessary Python dependency/configuration changes. Preserve the runtime assessment interface, input version and installed-package behaviour; coordinate any genuinely needed contract change before consumer changes. Do not edit `app/`, build a new framework, or reorganise the repository.

Deliver this as one implementation batch, with concise progress updates rather than approval pauses between ordinary steps:

1. Select a manageable official organiser package through the [data guide](../../data/README.md). Inspect source terms and record URL, hole ID, retrieval time, processing levels, file hashes, fields, units, masks and missing products. Read TSG products through inspected/pinned GSWA pytsg behind the scientific adapter. Prefer a small number of independent holes when feasible; do not download the full catalogue. Do not invent missing assays, mineral fields or spectra.
2. Implement the minimum QA and interval comparison needed for one real investigation family. Independently check selected calculations. Use the same validated scientific feature builder for training preparation and runtime request preparation; preserve source/tool/method versions and evidence references. Only offer actions supported by actual tools and data, with honest model action coverage.
3. Produce real-data question–instruction–observed-evidence–candidate records. Identify calculated-reference, teaching-rule and expert-reviewed labels accurately; do not invent expert review. Version any teaching rubric and retain it as a baseline. Include numerical-evidence-sensitive cases and differing legitimate questions on the same evidence, so training is not just fixed question-to-action matching. Never expose future outcomes or gold labels as pre-action features.
4. Freeze source partitions before record generation. Prefer independent hole/project groups for train/validation/test. If only one hole is usable, retain its true identity and use separated depth blocks with grouped overlapping windows and a documented separation buffer for a clearly labelled within-hole pilot only. Do not present block holdout as independent-hole generalisation. Insufficient defensible labels or source access must be reported honestly, never replaced with synthetic records labelled organiser.
5. Reuse the pinned Qwen3.5-4B LoRA/decision-head pipeline and prepared local model environment. Run actual bounded fine-tuning with `origin: organiser`, validated provenance and a matching configuration. Preserve the old synthetic artifact and write a new run directory. Record input hashes, counts, splits, label origins, parameter updates and actual training metrics. Use existing local resources; no additional paid compute or public model upload.
6. Evaluate the trained and untrained model on the same held-out records and compare with the teaching/reference baseline. Report per-action results and evidence-sensitivity checks; rule agreement alone is not geological usefulness or added value. Reload the saved artifact offline and produce a validated model-origin assessment from an actual real-data request. Verify that candidate coverage and runtime feature preparation match training; do not weaken validators. Retain the exact base/adapter/head bundle and integrity metadata.

Pass: inspected real sources, independently checked features, attributed labels, actual training, honest held-out results and offline real-request inference are demonstrated. No universal minimum row count or synthetic accuracy result substitutes for these checks. Run canonical checks and report actual current-head hosted CI. Ordinary CI uses small labelled fixtures; real packages, generated records, books, weights and detailed run logs remain ignored. The handoff includes reproducible commands, model/run version, source and label provenance, limitations and the new PR. Expert geological usefulness remains unproven until evaluated separately.

## Review and next gates

For the deadline delivery, follow the owner's [version-one submission gate](submission.md). Claude's immediate task is the [single real-data demo closeout](submission.md#claude-single-closeout-delivery) on `codex/claude-real-model`. The owner accepts the current model's accuracy limitation for version one; further training is deferred. This changes the release priority without weakening evidence integrity, scientific validation or immutable-history requirements.

Each worker pushes its own branch and opens a focused draft PR once there is a reviewable change. Do not merge directly into `main`. Review contracts first; then integrate backend/frontend without hiding fixtures or host limitations. Follow the canonical local check and report current-revision hosted CI separately.

Codex reviews architecture, correctness, evidence and scope; implementers own repairs. Model design, real-data supervision and fine-tuning remain in the owner's discussion with Codex. Useful model advice, automatic host continuation and a polished installer remain broader product goals; do not advertise them as complete or make them new version-one requirements. No package/plugin publication, licence selection or submission is authorised by these briefs.
