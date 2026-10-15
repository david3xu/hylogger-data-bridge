# Purpose: apply one worker result to the working page, fenced, validated and idempotent.
import json
import sqlite3
from datetime import datetime
from typing import Any

from hylogger_bridge.clock import stamp
from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.events.ack import complete
from hylogger_bridge.events.fence import fence
from hylogger_bridge.pages import actions
from hylogger_bridge.store import state

MAX_EVIDENCE = 200
PROGRESS = {
    "complete": "Evidence ready for your workflow decision",
    "partial": "Partial evidence ready for your workflow decision",
    "failed": "The work failed; the result is ready for your workflow decision",
}


def _replay(connection: sqlite3.Connection, completion: dict[str, Any]) -> bool:
    payload = json.dumps(completion, sort_keys=True)
    row = connection.execute(
        "SELECT payload FROM results WHERE request_id=?", (completion["request_id"],)
    ).fetchone()
    if row is None:
        return False
    if row[0] != payload:
        raise BookConflict("Request ID was already used for a different result", "request_reuse")
    return True


def merged(page: dict[str, Any], fresh: list[dict[str, Any]], outcome: str | None) -> list[Any]:
    """The page's evidence after adding more; a complete outcome must rest on complete evidence."""
    ids = [item["id"] for item in fresh]
    if len(set(ids)) != len(ids) or {item["id"] for item in page["evidence"]} & set(ids):
        raise ValueError("result evidence repeats an evidence ID")
    every: list[Any] = [*page["evidence"], *fresh]
    if len(every) > MAX_EVIDENCE:
        raise ValueError(f"a page holds at most {MAX_EVIDENCE} evidence items")
    if outcome == "complete" and any(item["state"] != "complete" for item in every):
        raise ValueError("a complete result cannot rest on partial or failed evidence")
    return every


def finish(connection: sqlite3.Connection, completion: dict[str, Any], at: datetime) -> None:
    """Move the working page to ready. Replaying the same result changes nothing."""
    validate("Completion", completion)
    if _replay(connection, completion):
        return
    book = state.read(connection)
    if not any(item["id"] == completion["page_id"] for item in book["pages"]):
        raise BookConflict("The result names a page that is not in this book", "unrelated_page")
    page = state.find(book, completion["page_id"], completion["expected_revision"])
    if page["status"] != "draft":
        raise BookConflict("Only the working draft can receive a result", "not_ready")
    job = connection.execute("SELECT status FROM jobs WHERE page_id=?", (page["id"],)).fetchone()
    if job is not None and job[0] == "running":
        raise BookConflict("The staged demo is still running on this page", "not_ready")
    step = fence(connection, page, completion["claim"], at)
    outcome = completion["outcome"]
    evidence = merged(page, completion["evidence"], outcome)
    actions.check(completion["action"], page)
    page.update(
        evidence=evidence,
        status="ready",
        outcome=outcome,
        errors=completion["errors"],
        summary=completion["summary"],
        progress=PROGRESS[outcome],
        action={**completion["action"], "actor": completion["worker"], "recorded_at": stamp(at)},
    )
    state.replace(book, page)
    if step is not None:
        complete(connection, step, at)
    payload = json.dumps(completion, sort_keys=True)
    connection.execute("INSERT INTO results VALUES (?,?)", (completion["request_id"], payload))
    state.save(connection, book, "page_ready", page["id"], f"Worker result applied: {outcome}")
