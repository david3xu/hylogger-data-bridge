# Application implementation tasks

Updated: 2026-10-14
Status: briefs prepared for the owner to give to implementers; no session contacted.

## Ownership and branches

| Owner | Branch | Initial scope |
| --- | --- | --- |
| Claude Sonnet | `codex/claude-backend` | Shared contracts, backend lifecycle and supported host-return feasibility |
| Gemini Argon | `codex/gemini-frontend` | Live book, assessment display and human decision interaction |
| Owner + Codex | No implementation assignment | Model/data design, fine-tuning approach, evaluation and architecture review |

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

## Review and next gates

Each worker pushes its own branch and opens a focused draft PR once there is a reviewable change. Do not merge directly into `main`. Review contracts first; then integrate backend/frontend without hiding fixtures or host limitations. Follow the canonical local check and report current-revision hosted CI separately.

Codex reviews architecture, correctness, evidence and scope; implementers own repairs. Model design, real-data supervision and fine-tuning remain in the owner's discussion with Codex. The product remains incomplete until actual local fine-tuning, useful advisory integration, verified scientific tools, separate host acceptance and clean installed-package behaviour are demonstrated. No package/plugin publication, licence selection or submission is authorised by these briefs.
