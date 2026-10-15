# Purpose: commit a human decision, lock its page, create its successor and queue its delivery.
import json
import sqlite3
import uuid

from hylogger_bridge.clock import now
from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.pages.make import new_page
from hylogger_bridge.store import cont, state

EXCERPT = 240


def _excerpt(note: str) -> str:
    """A bounded display line; the exact note lives only in the decision record."""
    text = note if len(note) <= EXCERPT else note[:EXCERPT].rstrip() + "…"
    return text or "Choose the next evidence to examine."


def decide(
    connection: sqlite3.Connection,
    page_id: str,
    expected_revision: int,
    choice: str,
    note: str,
    request_id: str,
) -> None:
    """All-or-nothing in the caller's transaction; replaying the same request changes nothing."""
    request = {
        "choice": choice,
        "note": note,
        "expected_revision": expected_revision,
        "request_id": request_id,
    }
    validate("DecisionRequest", request)
    payload = json.dumps([page_id, expected_revision, choice, note])
    seen = connection.execute("SELECT payload FROM requests WHERE id=?", (request_id,)).fetchone()
    if seen:
        if seen[0] != payload:
            raise BookConflict(
                "Request ID was already used for a different decision", "request_reuse"
            )
        return
    book = state.read(connection)
    page = state.find(book, page_id, expected_revision)
    if page["status"] != "ready":
        raise BookConflict("Evidence must be ready before a decision is recorded", "not_ready")
    stamp = now()
    successor = new_page(page["number"] + 1, page_id)
    successor["summary"] = f"Previous workflow choice: {choice}. {_excerpt(note)}"
    if book["source"] == "live":
        # A real case never inherits the synthetic template's question or progress text.
        successor["question"] = page["question"]
        successor["progress"] = "Waiting for a worker to continue from your decision"
    decision = {
        "id": str(uuid.uuid4()),
        "page_id": page_id,
        "choice": choice,
        "note": note,
        "request_id": request_id,
        "locked_revision": page["revision"] + 1,
        "successor_id": successor["id"],
        "evidence_ids": [item["id"] for item in page["evidence"]],
        "actor": {"kind": "human"},
        "recorded_at": stamp,
    }
    page["decision"] = decision
    page["status"] = "locked"
    state.replace(book, page)
    book["pages"].append(successor)
    book["current_page_id"] = successor["id"]
    cont.insert(
        connection,
        {
            "id": str(uuid.uuid4()),
            "decision_id": decision["id"],
            "page_id": page_id,
            "successor_id": successor["id"],
            "locked_revision": decision["locked_revision"],
            "state": "pending",
            "attempts": 0,
            "max_attempts": cont.MAX_ATTEMPTS,
            "claimed_by": None,
            "lease_expires_at": None,
            "acknowledged_at": None,
            "last_error": None,
            "created_at": stamp,
            "updated_at": stamp,
        },
    )
    connection.execute("INSERT INTO requests VALUES (?,?)", (request_id, payload))
    state.save(
        connection,
        book,
        "decision_recorded",
        page_id,
        "User workflow choice recorded; page locked and successor created",
    )
