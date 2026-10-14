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

## Acceptance

Observe evidence appear without reload. Submit a real UI choice and see a linked page open automatically. Verify previous-page content cannot be changed, duplicate submissions cannot create extra pages, stale worker results fail, and reconnect/reload preserves history. Test in the actual Codex browser before claiming integration. Maintain the existing selector tests.

## References

- [MDN SSE](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events): EventSource, IDs, reconnection and keepalive comments.
- [Codex browser](https://learn.chatgpt.com/docs/browser): viewing local development routes in the desktop browser.
- [Book design](design.md#live-book): templates, locked history and decision authority.
