# Three-condition SWMB007s pilot

Updated: 2026-10-15
Status: completed technical pilot; no expert-user study or general superiority claim.

## Outcome

Three independent GPT-6 Luna agents answered the same six requests using one real HyLogger package. Their generated outputs each matched **25/25 frozen scientific checks**. These are 25 fields from one case, not 25 independent experiments.

The toolkit preserved a structured review book and passed decision/continuation replay checks. The direct Python agent also saved its own evidence and exact notes. The pilot therefore supports a reusable review-workflow demonstration, not a claim that ordinary chat with Python cannot calculate or preserve evidence.

Actual Qwen advice recommended `clarify` at all three diagnostic checkpoints, agreeing with none of the three predeclared procedural follow-ups. This pilot demonstrates no added value from the fine-tuned advice. It also exposed an application defect when advice is disabled: the first fresh start raised an error after saving a ready page; retry recovered it. That failure is part of the result.

## Agent setup

The owner requested three separate subagents using GPT-6 Luna at extra-high effort. Codex acted as coordinator and independently calculated/scored the reference while the agents worked.

Each agent was launched through `collaboration.spawn_agent` with:

```json
{
  "model": "gpt-6-luna",
  "reasoning_effort": "xhigh",
  "fork_turns": "none"
}
```

`fork_turns: none` omitted the coordinator's conversation history. Every worker received the same task sequence, source folder, installed Python and output schema, plus only its condition-specific permissions. Workers were instructed not to inspect other arms, prior result reports or the coordinator's numeric reference. This was not a formally blinded study: project instructions and the procedural reference were available in the environment.

| Agent | Condition | Allowed implementation |
| --- | --- | --- |
| `pilot_direct` | A: Chat + Python/pytsg | Raw pytsg, NumPy/pandas and its own calculations/JSON records. No application imports, model, MCP or book APIs. |
| `pilot_toolkit` | B: Chat + toolkit/book; trained advice disabled | Installed `CaseRegistry` with a private cases directory and an unavailable provider. No trained inference or fixture ranking. |
| `pilot_qwen` | C: Chat + toolkit/book + actual Qwen | Same private registry workflow, plus the installed `ProcessProvider` and actual checkpoint. No fixture substitution. |

Each agent independently wrote and ran a script and produced six written answers. This was **not six live chat turns per arm**, a human-in-the-loop usability session, or a new browser/host-dispatch acceptance test. The test used the library behind the installed tools; it did not benchmark MCP discovery or ordinary chat adoption.

### Shared constraints and environment

- Same read-only `SWMB007s_chips/pkg` source. The four primary SWIR/TIR file hashes matched across all conditions and the independent reference.
- macOS 26.6.2 on Apple Silicon; Python 3.12.13; application 0.1.4; pytsg 1.0.0; NumPy 2.5.4; pandas 3.0.6. Application source: [`2a348aa`](https://github.com/david3xu/hylogger-data-bridge/commit/2a348aa001625b7fc3669b1e92296094efbb22d3).
- C used `qwen35-4b-109a5c50a485`, the existing Qwen3.5-4B LoRA/decision-head checkpoint. No retraining or parameter changes.
- Metre intervals were half-open: `[top, bottom)`.
- No internet, dependency installation, application repairs or shared-service changes during the experiment. C needed host Metal access for local inference; its first sandbox attempt failed without that access.
- Separate temporary output/cases directories; no global MCP tools, session binding or queue notifications. Owner books and account configuration were outside the experiment.
- Target completion was about seven minutes per agent within a ten-minute investigation window. Documentation and GitHub publication followed the completed runs.
- Accept/modify/reject were fixed **automated evaluation inputs**, explicitly labelled `AUTOMATED EVALUATION INPUT; NOT EXPERT VALIDATION`. Notes included whitespace, newline and Unicode. Each arm used its own note wording, so notes were checked against that arm's inputs, not against identical text across arms.

## Six requests

| Step | Request | Scripted review input |
| --- | --- | --- |
| 1 | Review SWMB007s. Check coverage and quality for 0–5 m and 5–10 m; open the book if the condition supplies one. | None |
| 2 | Compare the TSG-interpreted SWIR groups in these intervals. | Accept |
| 3 | What changed, and what are the limitations? | None |
| 4 | Compare target 10–15 m against reference 5–10 m instead. | Modify |
| 5 | Set aside this follow-up comparison and retain its evidence. | Reject |
| 6 | Summarise the findings, recorded decisions and model limitations. | None |

B and C started with target 5–10 m/reference 0–5 m, then used the same replacement bounds. The scripted decisions were applied only to private test books. No real expert judgement or browser choice is attributed to an agent.

## Reference and scoring

Before reading worker results, the coordinator froze a separate calculation using raw pytsg tables and pandas. It imported no application calculation, policy or model code. It used `Final Mask == 1`, decoded `Grp1 sTSAS`, excluded empty/INVALID/ASPECTRAL/NOTAROK interpretations, and derived expected positions from the package's sampling grid.

Scientific scoring compared:

- Seven fields for each of three intervals: total spots, valid spots, excluded spots, expected positions, covered positions, interpreted spots and the group-count dictionary: 21 checks.
- Two fields for each of two comparisons: total variation distance and dominant-group change: four checks.

The checks were equality checks against the frozen reference, not an LLM judging its own answer. Both reference and workers used pytsg, so shared reader errors remain possible. This is independent calculation logic, not independent mineralogical ground truth.

The coordinator also reopened B/C SQLite books separately and repeated their exact completed continuation and decision requests. Each replay returned the existing result without changing the full snapshot. Four pages, three sealed scripted decisions and three completed continuations remained; the final action was `stop`.

### Scientific results

| Interval | Valid / total | Covered / expected | Excluded | Interpreted primary SWIR group |
| --- | --- | --- | --- | --- |
| 0–5 m | 5/5 | 5/5 | 0 | KAOLIN: 5 spots |
| 5–10 m | 5/5 | 5/5 | 0 | SMECTITE: 5 spots |
| 10–15 m | 5/5 | 5/5 | 0 | SMECTITE: 5 spots |

The 5–10 m versus 0–5 m comparison had total variation distance **1.0**, with a dominant-label change. The 10–15 m versus 5–10 m comparison had distance **0.0**, with no dominant-label change. These describe TSG interpretations; they do not establish mineral abundance, a geological boundary, assay results or resource estimates. Data attribution and licence are in [data handling](../../data/README.md).

### Condition results

| Observation | A: direct Python | B: toolkit, advice disabled | C: toolkit + Qwen |
| --- | --- | --- | --- |
| Scientific field checks | 25/25 | 25/25 after recovered start | 25/25 |
| Saved exact scripted notes | Yes, custom JSON | Yes, book | Yes, book |
| First comparison retained after modification | Yes, separate JSON evidence | Yes | Yes |
| Reopened saved records | Yes | Yes | Yes |
| Duplicate decision/continuation protection | Not implemented/exercised | Passed | Passed |
| Reject stopped further calculations | Script followed stop input | Book action `stop` | Book action `stop` |
| Persistent application review book | No | Four pages | Four pages |
| First-pass execution limitations | No product repair | Fresh no-advice start failed; identical retry recovered | Metal sandbox failure and harness-only preparation failure; corrected final run succeeded |

A's lack of replay protection means only that the agent did not implement it in this run. Python can implement equivalent persistence and guards. We did not measure how much effort that would require.

B/C used application calculations and persisted measurements. Their scripts also used the application's pytsg-backed `Hole` to supply exact structured counts requested by the scoring schema. Some of these counts already appear in the book's readable evidence, but are not all separate numeric fields in its tool response. The score covers the agents' complete outputs, not only unmodified default chat/tool responses.

### Qwen diagnostic advice

The C agent made three additional requests to the same loaded checkpoint, using the real initial comparison's inventory, QA and comparison evidence respectively. Gold labels were not included in model inputs.

| Observed state | Predeclared procedural follow-up | Actual top advice |
| --- | --- | --- |
| Inventory; check quality first | `qa_check` | `clarify` |
| QA available; compare the intervals | `interval_compare` | `clarify` |
| Comparison complete; summarise evidence | `stop` | `clarify` |

Agreement was **0/3 diagnostic examples**. The reference is a workflow rubric, not expert geological labels; this is not a general accuracy estimate or a replacement for the [held-out training evaluation](training.md#r1-real-data-pilot). Actual scripted execution continued according to the test inputs despite the advice.

### Timing observations

| Reported segment | Elapsed seconds |
| --- | ---: |
| A: script imports, reading, calculation and initial persistence segment | 0.558 |
| B: reported workflow segment, including failed start and retry; excluding imports/registry construction | 0.848 |
| C: model initialization | 8.853 |
| C: ordinary workflow after initialization | 1.118 |
| C: three extra diagnostic advice calls | 1.928 |

These are worker-reported single-run execution segments with different timing boundaries. They exclude agent thinking, script authoring, actual human review and browser/host interaction. Workers ran on one shared machine, with contention and cache effects uncontrolled. **Do not rank efficiency, calculate a speedup or claim expert time savings from this table.**

## Failures and method deviations

1. **Product defect: unavailable advice can fail the first start.** B used an `UnavailableProvider` subclass returning status `unavailable`, empty suggestions and explicit evaluation-disabled metadata. `finish_first` saved a ready page, then indexed `advice["suggestions"][0]` while building its return value. This raised `IndexError`. The same-criteria retry reused the saved page and completed the workflow. The coordinator independently reproduced the failure in a second private fresh case. Fix empty-advice handling and add a first-start regression before claiming robust no-advice operation. No repair was made during this evaluation.
2. **Misleading unavailable-advice description.** The unavailable provider uses contract origin `fixture`. The generated limits text checks origin rather than unavailable status and calls it labelled fixture advice, although no suggestions/ranking were provided. Its status should remain explicit to users. This was recorded, not repaired.
3. **Baseline method differed.** A added finite-spectrum, `HyLogDiag == good` and `NumFeats >= 24` checks and assumed metre-centred positions. These were the agent's choices, not a validated shared QA standard. All selected rows met them, so results matched here. Missing rows, irregular grids, rejected interpretations and tied dominant groups were not compared; the methods are not established as equivalent beyond this example.
4. **C preparation failures are retained in the record.** Its first default-sandbox model launch failed because Metal was unavailable. A later actual-model trial completed the workflow but its harness then read an incorrect summary field (`evidence` instead of `readable_evidence`). The harness was corrected and a fresh private final case succeeded; the earlier trial book was removed by that worker. Final numbers describe the corrected run. Preparation attempts are not counted as model/scientific errors or silently erased from this account.

## Reproduction and evidence handling

Use the [installed preview](install.md), the [developer data instructions](develop.md#reproduce-the-real-data-case) and the recorded package versions above. Keep one fresh private output root with `a/`, `b/`, `c/`, and a coordinator-only reference directory. Do not reuse an owner's live cases.

For each agent, provide the six requests, allowed libraries, fixed test-choice sequence, read-only package path, the same installed Python, and a private output path. Require a runnable script, log, structured results, six written answers, source hashes, failure history and timings. Prevent the direct arm from importing `hylogger_bridge` or training code. For B, use an unavailable provider with a clear disabled-by-evaluation limitation and no suggestions. For C, use `ProcessProvider(model_folder, installed_python)`; never replace a failed model with fixtures. Do not bind these fixture books to a chat session.

For B/C, start through `CaseRegistry`, record labelled private test choices through the store, and pass exact continuation/decision IDs to `continue_case_tool`; supply target `[10,15]` and reference `[5,10]` on modification. Reopen records and replay completed IDs. Derive a raw-pytsg reference independently before examining worker results, then compare the 25 named fields. Inspect failure logs as well as success summaries.

The local record contains protocol/environment JSON, reference/scoring/audit scripts, three runnable worker scripts, output JSON, answers, logs and private books. Raw packages, private books and complete generated records are **not published in Git**. This Markdown publishes aggregate findings and the method; it is not a public archive of every executable artifact. Frozen result SHA-256 values identify the retained local evidence:

| Artifact | SHA-256 |
| --- | --- |
| Protocol | `4a02fbafaa09ee55e0b5411b13e3e1b1cc08233b2686eba9f01df5dbf984805e` |
| Independent reference | `3f5e73882246fe6cca0dd309f029495b26d86e88c67369715da37a0916f9c13a` |
| A results | `bff94c21baf4309a70bf2fe78dbe861a93f39a74cf8bc59e9a9277a575469cf2` |
| B results | `d7037252c4723d65b8fe330076782e644aff312e358d4146126c885e5b2d892d` |
| C results | `ce39e0365b031e67b7d60682240423f6f8b1a974777bea29717a1527e145c0b4` |

## What the pitch can say

> In a one-hole technical pilot, three GPT-6 Luna agents obtained matching calculations. The toolkit additionally exercised a persistent, replay-safe review workflow. The local model's advice did not improve these diagnostic examples, and an optional no-advice startup defect was identified.

Do not claim better geology, faster expert work, superior numerical accuracy, general model usefulness, or measured adoption. Those require a larger study with agreed methods, identical timing boundaries and independent geologist review.
