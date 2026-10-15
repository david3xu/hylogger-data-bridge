# Version one: demo and submission readiness

Updated: 2026-10-15
Audit baseline: remote main `75bcb4f` plus the `codex/plugin-ready` repair branch. Implementation checks and remaining gates, not release approval.

## Owner decision and delivery boundary

### Technical ownership handover

The owner returned technical coordination, architecture and independent review to **Codex** after Claude Desktop's coordination interval. Current assignments supersede the previous handover. Implementation collaborators receive briefs through the owner's manual copy/paste relay and return handoffs the same way. A prepared brief or GitHub comment does not wake another worker. Preserve worker checkouts and branches. The old review heartbeat remains paused.

The first target remains a submission-ready real-data demonstration. The owner accepts the current model's poor accuracy as a disclosed experimental limitation. No retraining, model publication, paid compute or new scientific scope is needed for this deadline.

Theme: **Data Adoption**. Application: expert drill-hole evidence review supporting resource evaluation. The case compares two intervals of SWMB007s using QA and TSG-interpreted SWIR groups. The geologist remains the expert; technical test decisions are not geological validation. No assays, resource estimate, grade or proof of mineralisation are supplied.

Deadline: **15 October 2026, 11:59 pm AWST**. Judges use the default-branch revision at the deadline. The captain handles the [Team submission form](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026/issues/new?template=submission.yml), slides, declarations and required confirmations. Technical coordination does not grant submission, terms acceptance, licence selection or publication permission.

## What is verified

The initial independent audit used isolated archives of remote main `52d127a` and [PR #14](https://github.com/david3xu/hylogger-data-bridge/pull/14) head `72c51b1`. PR #14 subsequently merged as `75bcb4f`. Codex's repairs are in a separate managed worktree on `codex/plugin-ready`; other worker checkouts and real user books are preserved. The root working checkout may lag remote main.

| Area | Verified evidence and limit |
| --- | --- |
| Repository | Public; remote main `75bcb4f` includes PR #14 and the preview plugin |
| Main checks | Independent Python 3.12 run: 259 tests passed. [Main CI](https://github.com/david3xu/hylogger-data-bridge/actions/runs/38690476222) succeeded |
| PR #14 checks | Independent Python 3.12 run: 272 tests passed; Ruff, runtime/training mypy and doc links passed. Both hosted checks succeeded, including the [PR run](https://github.com/david3xu/hylogger-data-bridge/actions/runs/38702659439). These do not cover the release defects below |
| Real science | Existing SWMB007s package read with archived main code and the existing science environment. Both intervals have 5/5 valid spots and complete inferred grid coverage |
| Readable comparison | Reference 0–5 m: KAOLIN 5/5; target 5–10 m: SMECTITE 5/5; total variation distance 1. These are TSG interpretations, not fresh mineral identification or abundance estimates |
| Real-data lifecycle | Independent isolated technical TEST books: accept performs comparison; reject stops. Locked pages remain identical after reopening |
| Prior acceptance reports | A1 browser/restart/replay and C fresh-clone results are reported in the owner handoff. This audit did not independently repeat those full procedures or inspect slide 9 |
| Repair checks | Full canonical check passed on the repair worktree: 293 Python tests, 42 frontend tests, formatting/lint, strict types, documentation links, installed-wheel probe and production build. Hosted CI is a separate pending gate |
| Local model | Actual offline inference through the new persistent process boundary produced a ready real SWMB007s page with `origin: model`, version `qwen35-4b-109a5c50a485`, in 11.77 seconds including load. Advice remains collapsed to clarify, not a useful selector |
| Expert plugin | Six expert tools and skill; supported local marketplace installation succeeded. The installed cache launcher works outside the checkout without shell exports. Ordinary-chat selection remains unverified |
| Fresh clone report | AGY reproduced the developer route on `75bcb4f` with an existing source archive and technical API decision. Its setup/path findings are repaired here; this is not expert validation or host acceptance |

Detailed training evidence belongs in [training](training.md); judge-facing commands belong in the [README](../../README.md).

## PR #14 defects and repairs

The [independent review](https://github.com/david3xu/hylogger-data-bridge/pull/14#issuecomment-6187491350) records exact file/line references, reproductions and expected regressions. The six findings below are repaired and covered by focused regressions on `codex/plugin-ready`; its own tests are implementation evidence, not independent approval.

| Priority | Reproduced issue | Required repair |
| --- | --- | --- |
| P1 | Portable plugin.json has an unsupported root skills field; mcp.json lacks required schema/type | Validate the documented portable/compatibility layout and test cached installation |
| P1 | Fractional case IDs are rejected by later tools; formatting aliases distinct bounds | Stable allowed identity for exact criteria, stored-criteria verification and collision regressions |
| P1 | open_book returns success after readiness timeout and can reuse another book's endpoint | Confirm authoritative case identity/readiness; surface launch errors and handle competing starts |
| P1 | Smoke test deletes the normal SWMB007s case before prerequisites are checked | Disposable registry and owned-resource cleanup; preserve pre-existing books/processes |
| P1 | Nested package symlinks can escape the authorised root | Resolve and validate final discovered/read paths inside the selected scope |
| P2 | Failed initial advice leaves an unrecoverable reused draft | Resumable or explicitly recoverable preparation preserving measurements/provider truth |

The repaired smoke script always uses a disposable registry and labels fixture advice explicitly. Its failure regression preserves a pre-existing sentinel book. Never run the old destructive script from `75bcb4f` in a normal user registry or kill unrelated services to fix startup.

## Remaining release checklist

| Gate | Status | Owner / proof |
| --- | --- | --- |
| Plugin repair | Implemented; PR/hosted CI pending | Codex on isolated `codex/plugin-ready`; regression tests and safe real-data smoke |
| Independent repair audit | Open | A separate review is still needed; implementer checks are not independent approval |
| Actual plugin install | Supported CLI install and cached launch verified | User configuration locates the retained checkout, selected data folder and optional model environment. Actual GUI tool selection is the next gate |
| Codex normal-chat acceptance | Unverified | Fresh chat selects tools from an ordinary expert prompt, displays the real book, reads an owner decision and returns the correct successor after explicit follow-up |
| Browser recovery | Final release candidate still needs acceptance | Exact notes, locked history, reload/restart, duplicates and failure recovery on the final reviewed revision |
| Fresh clone | Earlier C result reported; plugin route unverified | Follow final README/plugin guide; identify author-local assets and model limitations |
| Default branch | Preview integrated; repair branch pending | Integrate only reviewed repairs with passing current checks; record deadline SHA |
| Documentation | Updated in repair branch | Setup, cached installation, actual model selection and manual continuation are documented |
| Data hygiene | Final check open | Inspect tree/history and package contents; exclude raw packages, generated records/books, weights, credentials and private paths |
| Slides | Not inspected in this audit | Readable final deck, PDF preferred, max 25 MB; distinguish demo, tested preview and future product |
| Team/licence/AI declaration | Owner/captain items unverified | Confirm team/captain details, owner-selected licence against organiser requirements, data attribution and AI declaration |
| Submission | Unverified | Captain supplies issue URL and confirms submission before the deadline |

## Host and product boundaries

### Installed-product readiness

Codex is preparing the installed runtime on `codex/product-install`, based on `977bcd2`, separately from AGY's `codex/agy-return`. The wheel now carries the built book, plugin and schema; it installs the scientific reader and exposes setup, diagnostics and bounded model preflight. The owner subsequently authorised a GitHub public preview containing the existing model, with held-out reference measurements excluded from the public manifest. The installer manages Python/runtime dependencies; standalone review is available without the pending host adapter. See [current implementation evidence](../../CLAUDE.md#commands). Nothing is published to PyPI or a public plugin/model directory.

Normal setup does not pin a data folder. At use time, the supported host must provide the authorised workspace for the current conversation. The source --data-root route remains a developer override. The current package intentionally refuses that automatic workspace mode until AGY's adapter is integrated, rather than scanning an assumed directory.

| Product gate | Current state |
| --- | --- |
| Wheel/UI/science installation | Built and checked outside the checkout; real published-reader QA reproduced |
| Local model startup | Actual installed bundle preflight passed; first cold service start previously timed out, so installation now preflights before registration |
| Workspace follows the current chat | AGY integration pending; folder changes, nested packages and same hole names in separate workspaces need acceptance |
| Automatic decision return | Queue probe received in this Codex conversation; bound-case decision, retrieval and successor completion remain unverified |
| Book automatically opens beside chat | Needs proof through the actual host agent, separately for Codex and ChatGPT Work |
| ChatGPT Work | No complete host acceptance yet; Codex ingress does not certify it |
| Fresh machine / distribution | Isolated-profile installation is partial evidence; physical-machine, upgrade/recovery, signing/notarization and supported distribution still need release checks |
| Public package/model/plugin publication | Not authorised or performed by this implementation batch |

The first AGY adapter delivery is [PR #16](https://github.com/david3xu/hylogger-data-bridge/pull/16), reviewed at `a485c22`. The [independent feedback](https://github.com/david3xu/hylogger-data-bridge/pull/16#issuecomment-6189016181) reproduces unbounded queue calls when dispatch-state persistence fails, a still-pending continuation not retargeted after session rebinding, and failure when the desktop CLI is absent from PATH. The browser also claims queued return without authoritative dispatch status. These repairs, an accessible stop/unbind operation, the workspace-mode interface and actual case-bound host acceptance remain open. A received capability probe and green fixture CI do not close those gates.

The target remains install once, select an authorised supported folder and converse normally. A localhost page does not invoke a model. Version one can use **explicit chat continuation**: commit in the book, return to chat and say the decision is made; a tool verifies it before acting. Automatic browser-triggered model continuation is separate and unimplemented.

The owner's subsequent clarification retains automatic updates in both directions as a product acceptance requirement. The explicit route can demonstrate the engine but is not completion of that requirement. A lightweight decision watcher must wake the correctly bound host investigation only for new committed work; unchanged heartbeat checks do not invoke an LLM. See [decision return](design.md#decision-return). The preview and PR #15 repairs do not close this host gate.

Do not assume ChatGPT Work universally requires a tunnel or remote endpoint. Local desktop and hosted web/cloud have different connection capabilities; verify each surface. Codex proof does not establish ChatGPT Work proof. End-user packaging, prebuilt assets, supported model distribution and per-user state remain separate gates.

Useful advice is not achieved. Expert labels may help future supervision, but no concrete cause of collapse or guarantee that more labels alone fixes it has been established. Keep model quality deferred without obscuring the reproducible scientific workflow.

## Claude single closeout delivery

The earlier Claude R1 closeout is integrated and is not a new assignment. Its historical audit is [available](https://github.com/david3xu/hylogger-data-bridge/pull/3#issuecomment-6183174878). Current work is repair review, host acceptance and submission closeout. Do not repeat completed R1 work or treat old checklist items as instructions to retrain or reimplement the engine.


### Public standalone preview acceptance

The owner authorised publication without waiting for the separate chat-return adapter. The [public preview release](https://github.com/david3xu/hylogger-data-bridge/releases/tag/v0.1.1-preview.1) has passed download/install and real-data book acceptance in a fresh local folder/profile; [canonical evidence](../../CLAUDE.md#public-preview-package) records the exact scope. It installs managed Python, scientific libraries and the existing experimental model. No source HyLogger data is distributed. Browser decision persistence, explicit continuation, duplicate replay and restart preservation passed on the installed runtime. This completes the standalone preview gate, not the connected-workspace chat, automatic return, ChatGPT, physical fresh-machine or model-usefulness gates.
