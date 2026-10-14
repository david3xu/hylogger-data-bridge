# GitHub implementation workflow

Updated: 2026-10-14
Status: the owner authorised a public GitHub repository, explicit document allowlisting and separate frontend/backend branches. The public remote is [david3xu/hylogger-data-bridge](https://github.com/david3xu/hylogger-data-bridge). Separate branch ownership is in [tasks](tasks.md). Hosted CI is established only by actual run results.

## Repository hygiene

Publish only source, tests, locked dependencies, small synthetic examples and essential documentation. `.gitignore` excludes Markdown by default and explicitly allows the root guide/instructions, data guide and maintained project documents. Internal planning notes and historical decision drafts remain local and ignored. Previously tracked preparation notes are removed from the current index without deleting local copies. Ignore rules do not erase prior Git history; the initial preparation commit was reviewed separately and contains no raw/private data or credentials.

Stage explicit paths and inspect the complete staged diff before pushing. Never force-add ignored notes, raw packages, books, model training records, credentials, caches or generated outputs. Do not select a licence, publish a package/plugin or submit an entry under repository-creation authorisation alone.

## Task branches and pull requests

Use one focused branch per task, with the default `codex/` prefix: for example `codex/t2-book` or `codex/t5-ui`. The prefix does not identify who wrote the code. Link each PR to its task ID and owner in the [task plan](tasks.md). The contract/schema PR should precede dependent implementation PRs.

Each implementer owns the paths in their brief. Shared schemas and dependency changes need a coordinated handoff; only the assigned owner integrates shared lockfile/build changes at a time; the first backend slice assigns Python configuration to Claude and frontend configuration to Gemini. Rebase or merge the current base before resolving a shared-contract change. Do not force-push another implementer's branch or mix unrelated repairs into a task PR.

Run the canonical local check from [CLAUDE.md](../../CLAUDE.md#commands) before requesting review. Open a draft PR early enough to inspect its concrete scope, then mark ready when its own checks pass and its evidence is complete. Run CI on draft PRs too. PR descriptions lead with resulting behaviour, then relevant validation, migration effects and limitations. Identify synthetic fixtures and unverified host support explicitly.

Codex reviews architecture, single responsibility, short informative names, correctness and evidence. Implementers repair their findings. An agent must not treat its own automated review as independent approval. Merge only after required checks pass on the current PR revision and review is resolved. Repository protection/rulesets must be configured separately; a YAML file alone does not protect `main`.

## Required CI behaviour

Keep `.github/workflows/check.yml` as the initial ordinary-validation workflow. Give the workflow and jobs stable, descriptive names so required-status rules do not drift. Its current single `check` job installs locked Python/Node dependencies and runs the combined check script. Preserve that shared entry point rather than maintaining a divergent CI-only set of checks.

| Concern | Required behaviour for the implementer |
| --- | --- |
| Triggers | Run on PR creation/update/reopen and pushes to `main`; permit manual reruns. Avoid running identical push and PR workflows for every feature-branch push. Add `merge_group` if a merge queue is actually enabled. |
| Required status | Start with the existing `check` job. Keep it emitted for every PR, including documentation-only changes. Add package checks as required only once their implementation exists and runs reliably. |
| Permissions | Set ordinary CI token permissions explicitly to read-only repository contents. No publishing credentials or model API keys are needed for fixture checks. |
| Concurrency | Group by workflow plus PR number, falling back to branch/ref. Cancel obsolete validation runs for the same PR/ref; never cancel unrelated implementers' runs. |
| Runtime | Set explicit job timeouts and use bounded local-service readiness checks. A missing local server must fail clearly rather than wait forever. |
| Dependencies | Use locked installs and supported Python/Node versions. Pin third-party Actions to reviewed commit SHAs, with their version recorded for maintainers; update pins through reviewed changes. |
| Caches | Key dependency caches from the relevant lockfiles and platform/runtime. Cache reusable dependency downloads, not user books, credentials, raw data or arbitrary workspace contents. |
| Outcomes | Formatting, lint, types, tests, docs and frontend build failures must fail CI. No blanket `continue-on-error`, unconditional success or retries that hide deterministic failures. |
| Review evidence | Record the actual run URL and checked revision in the PR. An old green run, cancelled run or local screenshot does not prove the latest code passed. |

GitHub documents the permissions and trigger/concurrency syntax, including the risk that filtered required workflows stay pending. Keep the initial required workflow free of top-level path filters. If selective checks become necessary later, retain an always-running gate that fails when an applicable dependency fails, is cancelled or is unexpectedly skipped. [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [Concurrency](https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency), [Required-check troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)

Do not use `pull_request_target` to build/run proposed source changes with privileged credentials. Normal implementation validation uses `pull_request` and synthetic/public fixtures. Keep publishing as a separate explicit operation with its own permission boundary. [GitHub security guidance](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)

## Checks by implementation phase

The exact executable commands and latest verified counts belong in `CLAUDE.md`; this document defines the required behaviour, not a second command/count registry.

| Phase | Automated evidence |
| --- | --- |
| Current prototype | Python formatting/lint/types/tests, local documentation links, frontend formatting/lint/types/tests and production build |
| Contracts and book lifecycle | Cross-language fixtures, migrations, decision/result idempotency, stale/locked writes, restart recovery and concurrent submissions |
| MCP and host bridge | Protocol/tool schemas, launch failure handling, installed resource loading, stdio output discipline and adapter tests |
| Local policy | Export/library agreement, schema/hash compatibility, standard-library offline inference and hard prerequisite enforcement |
| Installed package | Build wheel, inspect its allowed contents, install outside the checkout, load bundled UI/model and start from another working directory without Node or training libraries |
| Real scientific tools | Independent numerical fixtures and reproducible source/method metadata; real private/source datasets stay out of hosted CI |

The normal runner may download locked dependencies during setup. Offline-inference claims must be tested after installation with network access disabled or an equivalent controlled boundary, not inferred from the presence of a local model file.

Keep ordinary fixtures deterministic, small and independent of shared services. Do not call Datacore, paid LLM APIs, live ChatGPT sessions, public data downloads or training clusters on every PR. Tiny synthetic model-fitting tests may remain in CI; large training, real-data experiments and manual host acceptance are separate evidence. An SDK mock cannot certify that a real ChatGPT or Codex session resumed.

Use Linux for fast ordinary checks. The first installed-package target is macOS, so add a macOS clean-install check when the release task exists. Claim other operating systems only after their package/lifecycle cases are tested; do not build a speculative matrix for unsupported platforms.

## Artifacts and releases

Upload only an explicit allowlist of useful failure reports, synthetic screenshots or test package artifacts, with a short documented retention period. Never upload the full workspace or all of `outputs/`. Inspect package contents so raw data, private briefs, user SQLite books, caches and credentials cannot enter artifacts. Distinguish a CI artifact from a published release.

Normal PR/push CI must not publish to PyPI, GitHub Releases, plugin directories, a public demo or the hackathon submission. Once release is authorised, use a separate tag/manual release flow tied to a reviewed commit, with clean-install evidence and scoped publication credentials. Do not configure that flow to make every green implementation commit a public release.

## Response to a failing run

Read the failed step and preserve its diagnostic evidence. Reproduce the relevant failure locally, fix the cause in the task branch and push the repair. Rerun without code changes only for an identified transient infrastructure failure. Do not disable a required check, delete a meaningful regression test, relax assertions or mark a failing task complete merely to make the PR green. Document a real flaky-test limitation and its repair rather than silently retrying until it disappears.

The implementer's handoff includes the PR, checked revision, Actions result, local checks, migration implications and remaining manual host/domain evidence. Codex reviews that concrete result; no branch protection or release automation is established by this document.
