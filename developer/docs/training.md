# Local model training

Updated: 2026-10-14
Status: recorded training proposal for owner discussion; no dataset download, checkpoint selection or training implementation authorised by this document.

## Purpose and authority

The confirmed requirement is a locally installed fine-tuned model grounded in the organiser's HyLogger datasets, supplying decision support during an investigation. It advises the agent and human; scientific code performs calculations and the geologist retains final judgement. The assessment interface and application authority remain in [design](design.md#local-decision-model).

The proposed first experiment is a small pretrained encoder/ranker trained to score useful candidate follow-ups from the question, committed human instruction and observed evidence. This proposal is not a selected checkpoint, inference runtime or demonstrated performance result. The current synthetic logistic classifier remains a mechanics baseline and does not satisfy the requirement.

Model/data design stays with the owner and Codex. Gemini's frontend and Claude's backend can progress through the assessment contract with visibly labelled fixtures. Their initial briefs do not include scientific adapters, data preparation or model fitting; those need a subsequent bounded assignment.

Training task families must serve the [resource-evaluation evidence-review scope](design.md#mvp-scope-resource-evaluation-evidence-review). Do not broaden supervision to operational ore–waste, grade-control or other applications without a scope decision. The one-hole product demonstration does not replace independent source-group evaluation or establish model generalisation.

## 1. Inspect real packages

Select a manageable pilot hole, inventory its products and establish field semantics before constructing features. Identify additional independent holes/projects for evaluation if available. Record source URLs, retrieval times, licences, hashes, processing levels, depth fields, masks, units and missing products. Freeze source-group partitions before task generation, paraphrasing or fitted preprocessing. A one-hole pilot cannot establish cross-hole generalisation.

The organiser describes HyLogger/TSG products, linked assays and some geological classifiers. Those products do not establish expert labels for which investigation step to take next. The FAQ also identifies processing-level, mineral interpretation and assay-unit limitations that package inspection must consider. [GSWA data FAQ](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026/discussions/1)

Use the [data handling guide](../../data/README.md). Keep raw packages, private trajectories and generated training records ignored.

The proposed TSG input path uses [pytsg through our scientific adapter](design.md#tsg-ingestion-with-pytsg). The [S1 package-inspection task](tasks.md#s1--inspect-and-adapt-one-tsg-package) supplies verified mappings and initial calculation results. Offline preparation and live investigation must share adapter/method/feature definitions and record their versions. pytsg reads the source products; it neither creates next-action labels nor replaces independent checks or expert review. Assay inputs require a separately verified reader/linkage.

## 2. Construct grounded investigation records

Begin with bounded task families supported by the inspected products:

- Check whether an interval has adequate valid coverage for a requested comparison.
- Compare an interval with another specified section.
- Investigate spectral-change candidates and their overlap with available assays.

Define the required terminal evidence and independently check the scientific calculations. Construct intermediate states containing only information already observed through preceding actions. Include missing-evidence cases, legitimate alternative sequences, changes of direction and cases requiring clarification or an incomplete answer.

Illustrative teaching example only; these are not findings from a downloaded hole:

```text
Question: Compare this interval with the section above.
Human instruction: Check whether the difference survives removing masked samples.

Observed evidence:
  Both intervals have depth coverage.
  An initial comparison has been calculated.
  Mask sensitivity has not been checked.

Candidate actions:
  A. Repeat the comparison using valid samples.
  B. Retrieve assay records.
  C. Present the initial difference as the final answer.

Proposed teaching label:
  A preferred; C premature for the requested check.
  B's usefulness depends on the broader question.
```

The example explains the record structure; it is not expert-labelled supervision. In actual records, use real calculated features and result references. Unknown values stay unknown. Explicitly distinguish native missingness from controlled masking/removal. Do not teach one fixed action sequence with different hole names.

Each record should preserve:

| Fields | Purpose |
| --- | --- |
| Task ID, source group and split | Traceability and leakage control |
| Question and latest committed instruction | Actual user intent at the checkpoint |
| Pre-action revision, evidence references and bounded features | Information available before the choice |
| Candidate IDs, action types and bounded arguments | Meaningful alternatives |
| Acceptable actions, preferences/ties and label origin | Explicit supervision |
| Source/tool/method versions and reference outcome | Reproducibility and label audit |

## 3. Establish supervision

Compare valid candidate actions and bounded continuations against predeclared evidence requirements and costs. Determine whether an action resolves a relevant uncertainty, supplies required evidence, repeats work or leaves the question unsupported. Include clarification, presentation and stop where appropriate. Allow multiple acceptable actions and ties rather than inventing one uniquely correct sequence.

Record calculated-reference, teaching-rule, expert-reviewed and unresolved labels separately. An LLM can propose questions, candidates or teaching labels; its preference alone is not geological ground truth. Geological suitability claims require domain review. Deterministic references can establish narrower retrieval/calculation outcomes.

Future results and terminal outcomes may inform offline labels, but must not enter pre-action features. Keep all related windows, revisions, paraphrases and trajectories within their assigned source group. Fit numerical preprocessing using training groups only. A human accepting advice is feedback, not automatic proof that the advice was correct.

## 4. Fine-tune the ranker

Proposed scoring path:

```text
Question + instruction + observed evidence + candidate description
                    ↓
           Small pretrained text encoder
           + explicit numerical features
                    ↓
             Candidate usefulness score
```

Score each candidate, then return the ranking through the shared assessment interface. Numerical features include verified coverage, valid counts, masks/gaps, source availability and already calculated comparison/overlap quantities where relevant. Do not force the model to recover all numerical meaning from digit strings in text.

Start with preferred-versus-less-useful pairs where preference is justified. Use an appropriate ranking loss; tied or merely acceptable alternatives must not be turned into fabricated strict preferences. Fine-tune pretrained encoder parameters along with the scoring head. Record the base checkpoint, changed parameters, training configuration, seed, split manifest and saved artifact. A frozen encoder with a fitted head is a baseline, not the promised fine-tuning experiment.

Sentence Transformers documents supervised cross-encoder scoring/ranking training. It is a tooling candidate, not an approved dependency or an assurance that a particular architecture will work on our data. [Training documentation](https://www.sbert.net/docs/cross_encoder/training_overview.html)

Benchmark the candidate on the target laptop before committing to checkpoint/export/runtime: memory, latency, installation size and numerical output agreement matter. No hardware requirement or training duration has yet been measured.

Limit learned outputs to fields supported by supervision. Ranking labels do not automatically train evidence-gap judgments, calibrated uncertainty or explanations. Keep unsupported fields unknown or explicitly deterministic. Scores are not geological confidence.

## 5. Evaluate added value

Choose promotion criteria and cost weights before looking at held-out results. Compare on equal tasks, tools and budgets:

| Comparison | Question answered |
| --- | --- |
| Explicit rules | Is simple workflow logic sufficient? |
| Existing synthetic classifier | Does grounded training improve on the mechanics baseline? |
| Frozen encoder with fitted head | What do pretrained representations provide? |
| Fine-tuned encoder/ranker | Does updating pretrained parameters add value? |
| Same agent with and without local advice | Does advice improve complete investigations? |

Measure acceptable-action ranking, invalid/prerequisite-violating proposals, useful clarification/stop choices, answer correctness, evidence completeness, traceability and unnecessary calls. Report invalid proposals before backend filtering as well as executed outcomes. Enforced prerequisites must not make a poor model appear scientifically reliable.

Evaluate complete investigations on states produced by actual chosen actions, not only recorded teaching states. Hold the question fixed while varying observed evidence; hold evidence fixed while changing the requested task. Preserve failures and runs where advice worsens outcomes. Report source-group counts, label origins and expert-review coverage. A ranking score alone does not establish geological usefulness.

## 6. Export and participate in chat

Package trained weights, tokenizer, numerical preprocessing, schema/action versions, hashes and a model card with actual inference dependencies. Keep training dependencies separate. End users install a trained artifact; they do not retrain during setup or each interaction. Verify installed local inference without network access and compare exported outputs against the training implementation.

```text
Question / relevant tool result / committed human note
    → current evidence and candidate actions
    → local model assessment
    → agent/human considers ranked advice
    → independently validated action and scientific result
    → book records advice, actual action and evidence separately
```

Consult at meaningful investigation checkpoints. Read-only navigation, keystrokes and heartbeats never trigger inference. Advice may be declined without bypassing authorisation or scientific prerequisites. Refresh or label stale assessments; expose unavailable inference honestly.

## Next bounded step

Select and inspect actual packages, then review a small batch of grounded training records and their labels before selecting a checkpoint. Decide who implements the required scientific calculations before assigning training code. Frontend/backend work continues against the assessment interface. This record performs no download, fitting, model deployment or application implementation.
