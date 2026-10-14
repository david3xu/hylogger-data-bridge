# Purpose: claim the next pending delivery under a lease; end, return and recover claims.
import sqlite3
from datetime import datetime
from typing import Any

from hylogger_bridge.clock import parse, stamp
from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.events import runner
from hylogger_bridge.events.runner import RUNNER
from hylogger_bridge.store import cont, state, tries

SECONDS = 60
RUNNER_SECONDS = 600


def give_back(
    connection: sqlite3.Connection,
    step: dict[str, Any],
    at: datetime,
    error: dict[str, Any],
    ended: str,
) -> None:
    """End the current attempt without a result: retry while attempts and the error allow it.

    The next attempt starts unacknowledged; this attempt's receipt stays in its attempt record.
    """
    last = step["attempts"] >= step["max_attempts"] or not error["retryable"]
    changes = {
        "state": "failed" if last else "pending",
        "claimed_by": None,
        "lease_expires_at": None,
        "acknowledged_at": None,
        "last_error": {**error, "retryable": False} if last else error,
        "updated_at": stamp(at),
    }
    cont.update(connection, step["id"], changes)
    tries.mark(connection, step["id"], step["attempts"], {"ended_at": stamp(at), "ended": ended})
    detail = "Delivery abandoned; no attempts remain" if last else "Delivery returned for retry"
    state.log(connection, "continuation_changed", step["page_id"], detail)
    if step["claimed_by"] == RUNNER:
        runner.invalidate(connection, step["successor_id"])


def lapse(
    connection: sqlite3.Connection, step: dict[str, Any], at: datetime, reason: str, ended: str
) -> None:
    error = {"error": reason, "code": "delivery_failed", "retryable": True}
    give_back(connection, step, at, error, ended)


def expire(connection: sqlite3.Connection, at: datetime) -> int:
    """Return every running claim whose lease ended."""
    lapsed = [s for s in cont.in_state(connection, "running") if parse(s["lease_expires_at"]) <= at]
    for step in lapsed:
        lapse(connection, step, at, "The worker's lease ended before it finished", "expired")
    return len(lapsed)


def handoff(book: dict[str, Any], step: dict[str, Any], attempt: int) -> dict[str, Any]:
    page = next(item for item in book["pages"] if item["id"] == step["page_id"])
    decision = page["decision"]
    message = {
        "contract_version": 1,
        "continuation_id": step["id"],
        "decision_id": decision["id"],
        "run_id": book["run_id"],
        "page_id": page["id"],
        "successor_id": decision["successor_id"],
        "locked_revision": decision["locked_revision"],
        "attempt": attempt,
        "choice": decision["choice"],
        "note": decision["note"],
        "evidence_ids": decision["evidence_ids"],
        "actor": {"kind": "human"},
        "decided_at": decision["recorded_at"],
    }
    validate("Handoff", message)
    return message


def take(
    connection: sqlite3.Connection,
    step: dict[str, Any],
    worker: str,
    at: datetime,
    seconds: float,
) -> int:
    """Start the next attempt for one worker. It begins unacknowledged."""
    attempt: int = step["attempts"] + 1
    changes = {
        "state": "running",
        "attempts": attempt,
        "claimed_by": worker,
        "lease_expires_at": stamp(at, seconds),
        "acknowledged_at": None,
        "updated_at": stamp(at),
    }
    cont.update(connection, step["id"], changes)
    tries.begin(connection, step["id"], attempt, worker, stamp(at))
    detail = f"Delivery claimed (attempt {attempt} of {step['max_attempts']})"
    state.log(connection, "continuation_changed", step["page_id"], detail)
    return attempt


def claim(
    connection: sqlite3.Connection, worker: str, at: datetime, seconds: float = SECONDS
) -> dict[str, Any] | None:
    """Hand the oldest pending delivery to one worker; the attempt number fences its writes."""
    validate("Id", worker)
    expire(connection, at)
    waiting = cont.in_state(connection, "pending")
    if not waiting:
        return None
    attempt = take(connection, waiting[0], worker, at, seconds)
    return handoff(state.read(connection), waiting[0], attempt)


def adopt(
    connection: sqlite3.Connection, page: dict[str, Any], at: datetime
) -> tuple[str, int] | None:
    """Let the built-in synthetic runner hold the delivery that precedes this page, if any.

    Returns the exact (delivery, attempt) it now holds, or None when the page follows none. The
    runner acknowledges itself; that receipt says so and is not a host's acknowledgement. An
    exhausted delivery is refused: the runner never reopens work whose retries are used up.
    """
    step = None if page["parent_id"] is None else cont.for_page(connection, page["parent_id"])
    if step is None:
        return None
    expire(connection, at)
    step = cont.for_page(connection, page["parent_id"])
    if step is None:
        return None
    if step["state"] == "failed":
        raise BookConflict("This page's delivery used its last attempt", "delivery_failed")
    if step["state"] != "pending":
        raise BookConflict("A worker already holds this page's delivery", "page_locked")
    attempt = take(connection, step, RUNNER, at, RUNNER_SECONDS)
    cont.update(connection, step["id"], {"acknowledged_at": stamp(at)})
    tries.mark(connection, step["id"], attempt, {"acknowledged_at": stamp(at)})
    return step["id"], attempt


def release_runner(connection: sqlite3.Connection, at: datetime) -> None:
    """After a restart nothing is running: return what the synthetic runner held."""
    for step in cont.in_state(connection, "running"):
        if step["claimed_by"] == RUNNER:
            lapse(connection, step, at, "The synthetic runner was interrupted", "interrupted")
