# Version one: demo and submission readiness

Updated: 2026-10-15
Audit baseline: 10:40 AWST. Status is evidence-based, not a release approval.

## Owner decision and delivery boundary

### Technical ownership handover

The owner transferred technical coordination, review and integration to **Claude Desktop** on 2026-10-15. Claude Desktop may coordinate **AGY CLI** and the **Gemini app** to complete the project. Codex now represents the first-time user and evaluates the visible experience; it is no longer the scheduled implementation reviewer or integration gate. The earlier owner labels below are the audit snapshot; all remaining technical gates now belong to Claude Desktop and its assigned helpers. Captain submission/terms confirmations remain with the human captain.

The Codex review heartbeat is paused. Claude Desktop must read the [latest R1 audit](https://github.com/david3xu/hylogger-data-bridge/pull/3#issuecomment-6183174878), inspect current PR heads and take over the outstanding technical gates. Existing branch/path ownership protects concurrent work; coordinate deliberate handoffs rather than overwriting another checkout. Use an isolated Git-capable integrator for the known main-ancestry conflicts. Preserve the root checkout's uncommitted documentation, including this checklist and the changes in CLAUDE.md, design.md, tasks.md, training.md and .gitignore; they are not yet on remote main.

The owner selected a working real-data demonstration as the first target and accepts the current model's poor accuracy as a disclosed experimental limitation. Do not start another training run to improve the pitch. Real scientific calculations, truthful provenance, a complete human review cycle and reproducible commands remain required.

Theme: **Data Adoption**. Application: drill-hole evidence review supporting resource evaluation. Version one compares two intervals in one real hole, presents QA and available TSG-derived mineral-group evidence, records the local model's advisory response and lets a human record a review decision. It does not estimate resources, establish mineralisation or demonstrate assay overlap. No assays are available in the selected real-data path.

Deadline: **15 October 2026, 11:59 pm AWST**. Judges use the latest default-branch commit at that deadline. Captain submits the [official Team submission form](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026/issues/new?template=submission.yml). The organiser's [guidance](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026/discussions/1) explains the data and default-branch requirements.

## What is verified

These milestones are on separate branches unless explicitly identified as main. A checked implementation branch is not a submitted default-branch deliverable.

| Item | Evidence and limit |
| --- | --- |
| Public repository | [hylogger-data-bridge](https://github.com/david3xu/hylogger-data-bridge) is public; default branch is `main` |
| Initial installation instructions | Main's README has Python/Node setup and synthetic launch commands; real-data instructions remain unfinished |
| Backend lifecycle and transports | Reviewed backend handoff `00be233` in [PR #3](https://github.com/david3xu/hylogger-data-bridge/pull/3); hosted checks passed; still open |
| Frontend and backend integration | Actual browser evidence on integration revision `b479921`; later acceptance-runner repairs are in [PR #6](https://github.com/david3xu/hylogger-data-bridge/pull/6). Current head `c254669` has passing hosted checks but awaits the latest independent review |
| Real organiser data and calculations | Claude has prepared a bounded organiser-data collection and shared QA/comparison features. Previous independent source/feature checks passed. Raw packages remain local and ignored |
| Real-data repair source | `34ef673` is pushed on `codex/claude-real-model`; independent Python 3.12 suite and its full hosted push check passed. No R1 PR yet at this audit |
| Actual local fine-tuning | A separate real-data Qwen3.5-4B base/adapter/head bundle exists locally. It uses teaching-rule labels, not expert decisions |
| Offline reference agreement | Independent comparison of saved reload outputs to all training-end test references agrees; this is reload reproducibility, not useful model quality |
| Model quality limitation | Current trained predictions collapse to `clarify`; they do not outperform the constant majority-label baseline. Accepted for version one only with visible disclosure |
| Git data-path hygiene | Tracked files and locally available Git-history paths show no matching raw-data/model archive candidates. Repeat on the final integrated tree/history; this is not a comprehensive confidential-content certification |

Training methods and the eventual detailed R1 results belong in [training](training.md). Runtime commands belong in the final [README](../../README.md); do not substitute machine-specific private paths for judge-facing instructions.

## Remaining release checklist

Mark an item complete only with the named proof. Keep this file as the version-one readiness list rather than creating another competing status document.

| Gate | Status | Owner | Required completion evidence |
| --- | --- | --- | --- |
| Real-data book setup | Open | Claude | Fresh dedicated book identifies the actual hole and intervals, uses `source: live`, and has accurate question, progress and summaries |
| QA and interval comparison | Open for end-to-end demo | Claude | Real package is read through pinned pytsg; both intervals, units, coverage/masks, calculations and limitations are visible with source/method references |
| Actual local model advice | Open for repaired live path | Claude | Existing real-data bundle produces a validated assessment from persisted trusted features; version and experimental limitation remain visible |
| Human review and continuation | Open for real case | Claude + owner/Codex browser review | Page becomes ready; a real UI choice and exact note lock it and create one successor; an explicit worker claims/acknowledges and completes the next real-data step |
| Truthful evaluation | Open | Claude | Remaining validation gaps fixed; matching baseline/per-action and strictly controlled diagnostics generated from existing completed outputs; no retraining needed |
| Final R1 source handoff | Open | Claude | Explicit-path commit/push, draft PR against `codex/claude-delivery`, reproducible demo commands and full current-head CI |
| Frontend acceptance repair | Awaiting review | AGY, then Codex | Independently verify PR #6 `c254669`, including candidate/action comparison and production-boundary regressions; no feature expansion |
| Main integration | Open | Owner + Codex | Real Git integration of pinned main, backend, frontend and reviewed R1; resolve the known overlapping advice/check files, preserve all owned changes and pass current-head CI |
| Fresh-clone run | Open | Codex | Documented setup works outside existing caches; install pinned scientific dependencies, obtain the documented official package locally and reproduce the real case |
| Reload/restart and history | Open for final real case | Codex | Exact note, locked evidence and successor survive browser reload and service restart; duplicate completion does not change state |
| Public README/data guide | Open | Claude R1 section, then Codex integration | Exact package/hole download sources, exclusions, licence/attribution, installation, model setup/reproduction and real/synthetic launch distinction; disclose missing assays and model collapse |
| Final data/content hygiene | Open | Codex | Review staged changes, final tree/history and package contents; keep raw packages, generated training records, books, credentials and weights out of Git |
| Pitch slides | Unverified | Owner + presentation worker if assigned | Final readable PDF preferred, no more than 25 MB; explain the real case, architecture, observed results, AI use and limitations |
| Submission fields | Unverified | Captain | Team name, captain and members' names/GitHub IDs, Data Adoption theme, repo, summary, exact data used, AI declaration and slides link/upload |
| Captain confirmations | Unverified | Captain | Confirm public README, no committed data/confidential material, and organiser terms; create issue and retain its URL before the deadline |
| Deadline revision | Open | Owner + Codex | Record the final default-branch SHA and submission URL; do not rely on later pushes |

Model improvement, new data downloads, assay linkage, automatic chat continuation, cloud deployment, a new installer and package/model publication are deferred. A model-origin assessment is not evidence of automatic Codex or ChatGPT continuation. SSE keepalives maintain the browser connection only.

## Claude single closeout delivery

The [independent audit and copyable handoff](https://github.com/david3xu/hylogger-data-bridge/pull/3#issuecomment-6183174878) record the exact reviewed revision, reproductions and expected verification. Posting this comment does not resume Claude Desktop; the owner passes it into that session.

Work only in your existing isolated checkout on **`codex/claude-real-model`**, currently based on `34ef673`. Preserve pending `training/controlled.py`, `training/parity.py` and `training/provenance.py` work. Do not touch `app/`, another worker's checkout or main's merge ancestry. This is one bounded delivery with progress updates, not approval pauses between routine steps.

1. **Finish integrity repairs.** Validate finite numeric probabilities, range/sum and consistency of the reported winner in `training.evaluate.check`. Require all three controlled-input flags together. For the same-evidence/different-question diagnostic, keep the complete candidate criteria fixed as well as evidence. Add focused rejection regressions; keep ordinary imports lightweight. Record each controlled row's actual window length instead of the hard-coded five metres. Preserve the now-fixed controlled evidence-pair and model/rows identity checks.
2. **Close the existing evaluation.** The queued trained/untrained test and controlled inference jobs have finished. Reuse their outputs, verify identities/hashes, run the evaluator and reference-parity comparison, and write the provenance manifest. Distinguish captured training evidence from hashes reconstructed later from Git; a commit's blobs alone do not prove what a process loaded. Preserve the negative result and frozen test set. No new training run, sweep or metric target is required.
3. **Make a real book, through supported application operations.** Use one already downloaded verified package and explicit target/reference depth bounds. Give the new dedicated book `source: live` and truthful metadata; preserve default synthetic behaviour and old books. Use a small validated initialization/application path rather than patching SQLite JSON after the fact. Keep real evidence separate from synthetic geometry/assay examples. Add a focused regression for live metadata and readiness.
4. **Complete the review cycle.** Persist actual inventory/QA, obtain the existing real model's advice from trusted measurements, and finish the first page using the worker result operation. Provide a reproducible next-step command that, after a human decision in the browser, claims/acknowledges its continuation, attaches the actual scene, calculates interval comparison and finishes the successor. Preserve the old page and exact note. The worker is explicit; no invented automatic host dispatch. Never create an automated decision with actor `human`. Use an honest partial outcome when evidence is incomplete, and keep stale advice visibly stale after state changes.
5. **Return one reviewable handoff.** Provide exact commands to prepare, serve, inspect, advance and restart the real case with the existing frontend build. The model/science environment relay is acceptable if documented and request-checked; silently replacing model advice with a fixture is not. Update the R1 documentation with exact data used and limitations, run canonical checks, commit explicit owned paths, push, open the draft PR against `codex/claude-delivery` and inspect full current-head hosted CI. Return SHA/PR/CI, hole/intervals, model/run version, provenance/evaluation reports, actual demonstrated transitions and any remaining browser verification.

Done means the integrated frontend can display the real case and a human can review it, with an explicit worker continuing the investigation. A saved advice JSON or a draft page alone is insufficient. Judge-facing reproduction must not depend on ignored scratch wrappers or an author's absolute filesystem paths. Keep raw packages, generated records/books, detailed run outputs and model weights ignored; do not merge, submit, publish or purchase compute under this brief.
