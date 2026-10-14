# Local model training

Updated: 2026-10-15
Status: owner selected Qwen3.5-4B and authorised the initial fine-tuning feasibility implementation on 2026-10-15. Real HyLogger preparation remains a separate slice; no successful model training or local inference is claimed yet.

## Purpose and authority

The confirmed requirement is a locally installed fine-tuned model grounded in the organiser's HyLogger datasets, supplying decision support during an investigation. It advises the agent and human; scientific code performs calculations and the geologist retains final judgement. The assessment interface and application authority remain in [design](design.md#local-decision-model).

The owner selected Qwen3.5-4B with LoRA and a decision head for the first experiment. It scores useful candidate follow-ups from the question, committed human instruction and observed evidence. The previously proposed encoder/ranker remains a comparison candidate. Local export/runtime compatibility and useful performance must still be demonstrated. The current synthetic logistic classifier remains a mechanics baseline and does not satisfy the requirement.

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

Automatically labelling real-data states with a fixed `correct_action(state)` policy produces rule-distillation supervision. Real measurements do not turn those labels into expert knowledge or establish value beyond that policy. Retain the exact teaching rules as an evaluation baseline. Include cases where the same evidence supports different follow-ups for different questions or committed instructions, and where multiple actions are acceptable.

Do not label zero detected candidates as an unconditional stop: a valid negative result still needs supporting evidence and limitations. Missing assays may require a qualified partial answer or clarification, depending on the question. Availability flags and completion booleans alone cannot demonstrate evidence-sensitive advice.

Future results and terminal outcomes may inform offline labels, but must not enter pre-action features. Keep all related windows, revisions, paraphrases and trajectories within their assigned source group. Fit numerical preprocessing using training groups only. A human accepting advice is feedback, not automatic proof that the advice was correct.

## 4. Fine-tune the advisory model

### Encoder/ranker candidate

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

### Selected LoRA and decision-head experiment

Reviewed on 2026-10-15: Unsloth's [Qwen3.5-4B decision notebook](https://github.com/unslothai/notebooks/blob/main/nb/Qwen3_5_%284B%29-Decision.ipynb) uses `FastDecisionModel`, LoRA and a trainable decision head. Its dataset interface uses `state`, `questions` and `gold`; our internal records would need an explicit conversion. The notebook documents saving adapters, the decision head and calibration. It is a concrete feasibility starting point, not evidence of HyLogger performance or local Mac compatibility.

The notebook demonstrates the selected 4B configuration. Do not silently substitute the previously discussed 2B checkpoint. Record and pin the reviewed notebook/code revision and dependencies before any authorised experiment. Do not assume the notebook's generic row holdout supplies independent drill-hole evaluation; partition source groups before conversion and training.

Before substantial training, prove a small training/save/reload cycle and local inference on the target laptop. Preserve the base-model revision, tokenizer/input preparation, adapters, decision head, action mapping and any calibration. Downloading adapters alone does not demonstrate a complete runnable model. A CUDA/4-bit training configuration does not establish a supported Mac inference path. Compare local outputs with the training implementation and measure actual memory and latency. Stop the feasibility experiment for architecture review if the custom head cannot be loaded locally.

### Colab training infrastructure candidate

Reviewed on 2026-10-15: Google's [official Colab CLI](https://github.com/googlecolab/google-colab-cli) supports remote runtimes, execution of local scripts, dependency installation and checkpoint retrieval on macOS/Linux. `colab exec -f` transmits the script contents; imported project modules and input files must be uploaded or installed separately. Use a named runtime for a multi-step experiment and retrieve artifacts before releasing it. Hardware availability and compute entitlement must be checked; no particular GPU, duration or account balance has been verified for this project.

Keep developer-only preparation, training and evaluation code in this repository, with a separate pinned training environment. Keep raw packages, generated training records, weights and credentials outside Git. Colab is a candidate training service, not an end-user runtime dependency. The owner subsequently authorised this bounded implementation and training feasibility check. Use existing plan resources only; no additional compute purchase, public model upload or broad scientific-data download is included. Google account sign-in requires the owner to complete the provider authentication flow.

### Colab operating procedure

This records the substance of the supplied Option A proposal, with project-specific corrections. The official CLI is the script-based training path; VS Code is an optional editor. Keep the model work in this repository rather than creating a separate competing project. Use short developer-only modules under `training/` when implemented, a separate training environment, ignored inputs under `data/` and ignored results under `outputs/`. Generated real-data JSONL records remain outside Git; only separately reviewed small synthetic fixtures may be tracked.

1. Install the official CLI on macOS/Linux. The initial experiment installed version `0.7.4` in an isolated environment; the equivalent standalone installation is shown below. Let the owner complete Google's interactive sign-in. Do not paste OAuth codes, tokens or credential files into chat or source control.
2. Inspect compute usage and entitlement, then allocate one named runtime. GPU selection is subject to availability. The `T4` command below is illustrative, not a guarantee or a measured recommendation for Qwen training speed. Check actual device and precision support before training; prefer available bfloat16-capable hardware when appropriate.
3. Install the reviewed training dependencies remotely. Pin the reviewed Unsloth/code/checkpoint revisions and retain the resolved dependency versions. Broad unpinned package lists are not a reproducible environment.
4. Transfer the exact source revision and required input files. Executing a local script transfers its contents, not its imports, configuration or datasets. For multiple modules, install/upload a source bundle or clone and check out the exact Git commit remotely. Keep credentials out of bundles and avoid tunnels or a second public service.
5. Run preparation, training and evaluation in that named runtime so their files persist across steps. For the initial portability check, use clearly labelled synthetic teaching records. Real HyLogger states and labels are a subsequent data-preparation deliverable. Use bounded execution timeouts and periodic checkpoints; never assume `/content` is durable storage.
6. Export adapters, the decision head, tokenizer, base-model revision, input/action definitions, metrics and a dependency/run manifest. Create an explicit artifact bundle, download it and the run log, and verify its hashes before releasing the runtime. The offline inference package must also resolve all required base weights locally.
7. Stop the runtime after retrieval or on failure. Never leave an unattended GPU running merely because a local command failed. Do not automatically retry provisioning or buy additional units when entitlement is unavailable.

Official commands for the prepared source-bundle path; generate synthetic records and the source bundle before allocating a runtime:

```sh
uv tool install google-colab-cli==0.7.4
PYTHONPATH=src python -m training.smoke data/decision/smoke.jsonl
PYTHONPATH=src python -m training.bundle outputs/model/source.zip
colab usage
colab new -s hylogger --gpu T4
colab status -s hylogger
colab install -s hylogger -r training/colab.txt
colab upload -s hylogger outputs/model/source.zip /content/source.zip
colab upload -s hylogger data/decision/smoke.jsonl /content/records.jsonl
colab exec -s hylogger -f training/remote.py
colab download -s hylogger /content/model-run.zip outputs/model/model-run.zip
colab log -s hylogger -o outputs/training.ipynb
colab stop -s hylogger
```

For a genuinely standalone script, `colab run --gpu T4 train.py` provisions, executes and releases a fresh runtime. This does not synchronise a multi-module checkout, install its dependencies automatically or preserve uncollected artifacts. A named session is the initial preference for the multi-step experiment.

The same CLI commands can run in VS Code's integrated terminal. Google's [official Colab VS Code extension](https://github.com/googlecolab/colab-vscode) is an alternative for local notebook development: select the Colab kernel/server and GPU, then sign in. Extension capabilities/version and actual runtime access must be checked before claiming a working setup. Native Windows CLI support is not established by the reviewed CLI documentation; WSL compatibility has not been verified here.

Initial access check on 2026-10-15: the isolated CLI installed successfully; `colab usage` requested interactive Google authorisation and exited without a usage result. No account balance, GPU entitlement or remote runtime has been verified. The source proposal's precise launch date and claims of lowest friction were not independently established and are not project requirements. Its pasted HTML/CSS is presentation material, not implementation instructions.

## 5. Evaluate added value

Choose promotion criteria and cost weights before looking at held-out results. Compare on equal tasks, tools and budgets:

| Comparison | Question answered |
| --- | --- |
| Explicit rules | Is simple workflow logic sufficient? |
| Existing synthetic classifier | Does grounded training improve on the mechanics baseline? |
| Frozen encoder with fitted head | What do pretrained representations provide? |
| Fine-tuned encoder/ranker or LoRA decision-head model | Does updating pretrained parameters add value? |
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

For a quick demo, keep one bounded question family and only implemented scientific actions. Select and inspect actual packages, then review a small batch of grounded training records and their labels. For the selected Qwen3.5-4B experiment, prove save/reload and target-laptop inference early, fine-tune on the reviewed records and compare against the exact teaching rules on held-out source groups. One-hole results demonstrate mechanics, not unseen-hole generalisation. Do not promise a useful model merely from generating hundreds or thousands of rule-labelled states.

Decide who implements the required scientific calculations before assigning training code. Frontend/backend work continues against the assessment interface. The model recommends follow-ups; the agent/human chooses and the backend independently validates execution. Implementation is now authorised for the bounded model portability experiment. This document records intent and actual checks; it does not establish that a training run or deployment succeeded.

## Running the selected experiment

Model work is isolated on `codex/model-feasibility`, based on the reviewed contracts branch plus the scope/training documentation. The selected architecture is Qwen3.5-4B with a trainable decision head and LoRA adapters. `training/qwen.json` pins the Colab checkpoint; `training/mac.json` pins the MLX community 4-bit conversion of the same architecture for the first local run. Architecture/configuration were inspected; bitwise equivalence of those two source checkpoints is not asserted. Save their actual identifiers and hashes with each run.

| Path | Responsibility |
| --- | --- |
| `training/records.py` | Validate label provenance and independent source-group partitions; convert records |
| `training/smoke.py` | Generate explicitly synthetic portability records outside Git |
| `training/fit.py` | Train adapters/head, evaluate and export a complete merged checkpoint |
| `training/check.py` | Reload offline and compare saved predictions |
| `src/hylogger_bridge/advice/encode.py` | Shared bounded input encoding |
| `src/hylogger_bridge/advice/provider.py` | Validate actual option predictions and return assessment metadata |
| `src/hylogger_bridge/advice/assets.py` | Manifest and checkpoint integrity |
| `src/hylogger_bridge/advice/local.py` | Local model loading behind the provider interface |
| `src/hylogger_bridge/advice/cli.py` | One-request command-line access |

Developer invocation from the experiment checkout, using its isolated model environment:

```sh
PYTHONPATH=src cache/model-env/bin/python -m training.smoke data/decision/smoke.jsonl
PYTHONPATH=src cache/model-env/bin/python -m training.fit --config training/mac.json --records data/decision/smoke.jsonl --output outputs/model/smoke
PYTHONPATH=src cache/model-env/bin/python -m training.check outputs/model/smoke/merged
PYTHONPATH=src cache/model-env/bin/python -m hylogger_bridge.advice.cli --model outputs/model/smoke/merged --request outputs/model/request.json
```

The request file must contain a canonical AssessmentRequest. Predictions remain model advice, with training-data origin visible; rationales explicitly state that no explanation was generated. Missing/invalid candidate predictions, unsupported action types and over-budget inputs fail rather than becoming fabricated advice. Input encoding version and declared action coverage travel with the artifact. Organiser records require source hashes and processing provenance; the smoke records remain synthetic. `training/bundle.py` uploads an explicit allowlist of source files; `training/remote.py` extracts that bundle and runs the same fit/reload checks in Colab. The backend can use `LocalProvider.assess(request, at)` as its replaceable provider; inference must run outside the SQLite writer transaction. The adapter does not launch tools or create human decisions.

A generated smoke dataset demonstrates training mechanics only. Its repeated teaching situations are not independent geological cases, even though grouped partitions prevent exact source-group overlap. Use inspected organiser records and independent hole/project groups before making real-data or generalisation claims. A successful import, unit test or checkpoint download alone is not a successful training run.
