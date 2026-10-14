# Purpose: a repeatable synthetic walkthrough: decision, claim, evidence, result and reload.
import argparse
import json
import tempfile
import threading
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

from hylogger_bridge.book import BookStore
from hylogger_bridge.book_server import BookServer
from hylogger_bridge.contracts.book import check_book

LABEL = (
    "SYNTHETIC MECHANICS DEMONSTRATION. An explicit tool-driven worker moved the book through "
    "claim, acknowledgement, evidence and result over HTTP. No model was invoked and no host "
    "agent continued automatically: this is not Codex continuation. Evidence and advice are "
    "synthetic fixtures; nothing here is geological judgement."
)
NOTE = "Check the assay interval first."


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, path, None if body is None else json.dumps(body), headers)
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        if response.status != 200:
            raise RuntimeError(f"{method} {path} failed: {response.status} {payload}")
        return payload

    def book(self) -> dict[str, Any]:
        book: dict[str, Any] = self.call("GET", "/api/book")
        return book


def working(book: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = next(p for p in book["pages"] if p["id"] == book["current_page_id"])
    return page


def run(path: Path) -> list[dict[str, Any]]:
    """Walk the whole flow against a fresh book at `path` and return what happened, step by step."""
    store = BookStore(path)
    server = BookServer(0, store, path.parent)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    steps: list[dict[str, Any]] = []

    def note(what: str, **facts: Any) -> None:
        steps.append({"step": len(steps) + 1, "what": what, **facts})

    try:
        client = Client(server.server_port)
        page = working(client.book())
        store.start_demo(page["id"], page["revision"])
        store.run_demo(page["id"], delay=0)
        ready = working(client.book())
        note("The staged synthetic runner made page 1 ready", evidence=len(ready["evidence"]))

        body = {
            "choice": "modify",
            "note": NOTE,
            "expected_revision": ready["revision"],
            "request_id": "walkthrough-decision",
        }
        locked = client.call("POST", f"/api/pages/{ready['id']}/decision", body)
        delivery = locked["continuations"][0]
        note("A human decision was committed", delivery=delivery["state"], note=NOTE)

        claimed = client.call("POST", "/api/work/claim_delivery", {"worker": "demo-worker"})
        handoff = claimed["handoff"]
        exact = handoff["note"] == NOTE
        note("The worker claimed the delivery", attempt=handoff["attempt"], exact_note=exact)
        attempt = {"continuation_id": handoff["continuation_id"], "attempt": handoff["attempt"]}
        client.call("POST", "/api/work/acknowledge_delivery", attempt)
        note("The worker acknowledged its own attempt", by="demo-worker")

        successor = working(client.book())
        asked = {"page_id": successor["id"], "expected_revision": successor["revision"]}
        advice = working(client.call("POST", "/api/work/request_assessment", asked))["assessment"]
        note("Advice was recorded", origin=advice["origin"], model=advice["model_version"])

        evidence = {
            "id": "walkthrough-check",
            "label": "Assay interval check",
            "value": "Synthetic: the interval the human named was examined",
            "source": "Synthetic walkthrough, not a real result",
            "kind": "observation",
            "origin": "synthetic",
            "state": "complete",
        }
        sent = {**asked, "evidence": evidence, "claim": attempt}
        client.call("POST", "/api/work/submit_evidence", sent)
        note("Incremental evidence was accepted under the claim")

        current = working(client.book())
        result = {
            "contract_version": 1,
            "request_id": "walkthrough-result",
            "page_id": current["id"],
            "expected_revision": current["revision"],
            "claim": attempt,
            "outcome": "complete",
            "summary": "The named assay interval was examined (synthetic).",
            "evidence": [
                {
                    "id": "walkthrough-result",
                    "label": "Interval comparison",
                    "value": "Synthetic: the named interval overlaps the assay record",
                    "source": "Synthetic walkthrough, not a real result",
                    "kind": "calculation",
                    "origin": "synthetic",
                    "state": "complete",
                }
            ],
            "errors": [],
            # The worker chose its own action; the fixture ordering did not decide it.
            "action": {"type": "interval_compare", "assessment_id": advice["id"]},
            "worker": {"kind": "agent", "name": "demo-worker"},
        }
        client.call("POST", "/api/work/submit_result", result)
        final = client.book()
        check_book(final)
        done = working(final)
        note(
            "The successor page is ready",
            status=done["status"],
            outcome=done["outcome"],
            delivery=final["continuations"][0]["state"],
        )
    finally:
        server.shutdown()
        server.server_close()

    reopened = BookStore(path).snapshot()
    check_book(reopened)
    note("After a reload the book is identical", identical=reopened == final)
    return steps


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic worker-lifecycle walkthrough")
    parser.add_argument("--db", type=Path, help="a new book file; defaults to a temporary one")
    args = parser.parse_args()
    if args.db is not None:
        steps = run(args.db)
    else:
        with tempfile.TemporaryDirectory() as scratch:
            steps = run(Path(scratch) / "walkthrough.sqlite3")
    for item in steps:
        print(json.dumps(item))
    print(LABEL)


if __name__ == "__main__":
    main()
