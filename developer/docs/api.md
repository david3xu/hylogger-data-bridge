# Live book demo: implementation contract

Updated: 2026-10-14

The owner asked AI workers to create a simple real-time book demo in the Codex desktop browser. Implement React/TypeScript with Vite and a local Python service. Use SQLite persistence and SSE notifications after committed writes. No cloud service, scheduled automation, language-model API or real geological data is needed.

## Scope

Demonstrate a synthetic question: “Show spectral-change intervals that overlap assay records.” A user starts the example; staged synthetic evidence arrives on the working page. A real user decision locks that page and creates a linked new draft; the browser follows it. Historical pages remain readable. Reload/reconnect recovers saved state. A pause-following control permits reading history without navigation jumps.

This is a functioning UI/persistence/transport demo with synthetic results. The staged runner is not the trained policy or a scientific analysis engine. Decisions record workflow choices, not geological approval. Automatic chat transcription or discovery of Codex internal events is outside scope. A worker must explicitly submit results to the service for them to appear.

Next integration requirement: the submitted decision and note must return to an agent runtime so the investigation can continue. That path is not implemented by this demo. See [design](design.md#decision-return), including the missing general worker-to-ready transition. The existing SSE stream updates the browser; it does not invoke a language model.

## API contract

- `GET /api/book`: snapshot described below.
- `GET /api/events?after=N`: SSE events named `book_updated`, with `id` set to the persisted sequence and JSON `{sequence,type,page_id}`. On reconnection honour `Last-Event-ID`. Client refetches the snapshot. Optional `: keepalive` comments maintain the transport only; they never mutate pages or wake an AI worker.
- `POST /api/demo/start`: `{page_id,expected_revision}` starts staged synthetic evidence for that draft; returns `{started:true}`. Do not run a duplicate worker for the same page. Ready/locked pages cannot restart.
- `POST /api/pages/{id}/decision`: `{choice:"accept"|"modify"|"reject",note:string,expected_revision:number,request_id:string}`. Atomically record the actual user choice, lock the page, create its successor and append an event. Require ready state and matching revision. Retry the same request ID/body without making another page; reject conflicting reuse.
- `POST /api/pages/{id}/evidence`: explicit worker interface `{expected_revision,evidence:{id,label,value,source,kind}}`, where `kind` is `observation`, `calculation` or `limitation`. Updates only drafts and emits an event. Stale/locked writes return 409. Source text must clearly identify synthetic or actual provenance.

Snapshot:

```text
{run_id:"demo",source:"synthetic_demo",current_page_id,sequence,pages:[Page],events:[Event]}
Page = {id,number,parent_id,template,template_version:1,title,question,
        status:"draft"|"ready"|"locked",revision,summary,progress,
        evidence:[{id,label,value,source,kind}],
        decision:null|{choice,note,recorded_at},created_at,updated_at,
        scientific_review:"unreviewed",demo_running:boolean}
Event = {sequence,type,page_id,at,detail}
```

For this demo `template` is `investigation` for the initial page and `candidate_evidence` for successors. Event types include `page_created`, `demo_started`, `evidence_added`, `page_ready`, `decision_recorded`. Event IDs are monotonic. The single decision event represents the committed lock/create operation; clients obtain the complete result from the snapshot. The service binds loopback only and rejects cross-origin mutations. Vite proxies `/api` during development; the production build can be served by the Python service.

## Worker lifecycle

The snapshot is the contract v1 `Book` in [`schemas/v1.json`](../../schemas/v1.json): pages are immutable once locked, and delivery state lives in `continuations`. Committing a decision records one `pending` continuation in the same transaction. A worker then claims it, acknowledges it, writes evidence or a result under that claim, and the page becomes `ready`. Nothing on this path invokes a model; see [design](design.md#decision-return) for the host gate.

| Route | Body | Effect |
| --- | --- | --- |
| `POST /api/work/claim_delivery` | `{worker, seconds?}` | Returns `{handoff}` with the exact committed choice and note and the attempt number, or `{handoff:null}`. |
| `POST /api/work/acknowledge_delivery` | `{continuation_id, attempt, seconds?}` | The worker accepted its attempt; repeating renews the lease. |
| `POST /api/work/fail_delivery` | `{continuation_id, attempt, error}` | Gives the attempt back; retried while attempts remain (three). |
| `POST /api/work/submit_evidence` | `{page_id, expected_revision, evidence, claim}` | Adds one evidence item; `origin` and `state` may be stated and are kept. |
| `POST /api/work/submit_result` | a `Completion` | Moves the page to `ready` as `complete`, `partial` or `failed`; replaying a `request_id` is harmless, reusing it for different content is a conflict. |
| `POST /api/work/request_assessment` | `{page_id, expected_revision, candidates?, instruction?}` | Records labelled advice. |
| `POST /api/work/read_attempts` | `{continuation_id}` | Every attempt with its own acknowledgement. |

Every write to a page that follows a delivery is fenced: it must present the current `attempt` from its own Handoff, hold an unexpired lease and have acknowledged. An old attempt, an expired lease, an unacknowledged claim or another page's claim is refused, including on `POST /api/pages/{id}/evidence`, which takes an optional `claim`. A claim is a fencing token, not authentication. A new attempt starts unacknowledged; earlier receipts stay in their attempt records. Refusals carry `{error, code, retryable}`: `claim_expired`, `not_ready`, `unrelated_page`, `stale_revision`, `page_locked`, `request_reuse`, `invalid_request`, `not_found`.

The staged synthetic runner is a built-in worker: it takes and acknowledges the delivery itself, is bound to its exact attempt, and is refused when a delivery has used its retries. Advice (`origin: fixture` until a trained model exists) never authorises an action; a result may name any registered action and cites the advice it consulted only if that advice is recorded on the page. Inference runs outside any database transaction: the request is validated and named as the page's latest ask in one short transaction, and the advice is recorded in another only if that ask is still the latest and the page has not changed or locked, so a slow older ask can never replace newer advice. A malformed `candidates` element is an `invalid_request` and never reaches the provider. `POST /api/demo/start` binds the started run to its own callback, so a late callback cannot adopt a replacement run.

`hylogger-mcp --db <book>` exposes the same operations as MCP tools over stdio (stdout carries only JSON-RPC). No operation records a human decision or scientific approval. `hylogger-walkthrough` runs the whole flow against a fresh book and prints each step; it is a synthetic, tool-driven mechanics demonstration, not Codex model continuation, which remains unverified.

## Acceptance

Observe evidence appear without reload. Submit a real UI choice and see a linked page open automatically. Verify previous-page content cannot be changed, duplicate submissions cannot create extra pages, stale worker results fail, and reconnect/reload preserves history. Test in the actual Codex browser before claiming integration. Maintain the existing selector tests.

## References

- [MDN SSE](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events): EventSource, IDs, reconnection and keepalive comments.
- [Codex browser](https://learn.chatgpt.com/docs/browser): viewing local development routes in the desktop browser.
- [Book design](design.md#live-book): templates, locked history and decision authority.
