# Purpose: let the current claim holder acknowledge, fail or complete a delivery.
import sqlite3
from datetime import datetime
from typing import Any

from hylogger_bridge.clock import stamp
from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.events import runner
from hylogger_bridge.events.claim import SECONDS, expire, give_back
from hylogger_bridge.store import cont, state, tries


def current(
    connection: sqlite3.Connection, continuation_id: str, attempt: int, at: datetime
) -> dict[str, Any]:
    """The running delivery, only for the attempt that still holds an unexpired lease."""
    expire(connection, at)
    step = cont.get(connection, continuation_id)
    if step is None:
        raise BookConflict("Unknown delivery", "not_found")
    if step["state"] != "running" or step["attempts"] != attempt:
        raise BookConflict("This delivery claim is no longer current", "claim_expired")
    return step


def acknowledge(
    connection: sqlite3.Connection,
    continuation_id: str,
    attempt: int,
    at: datetime,
    seconds: float = SECONDS,
) -> None:
    """The worker accepted this attempt. Repeating it only extends the lease.

    The timestamp is the worker's own acceptance, never inferred from transport success.
    """
    step = current(connection, continuation_id, attempt, at)
    changes = {"lease_expires_at": stamp(at, seconds), "updated_at": stamp(at)}
    if step["acknowledged_at"] is None:
        changes["acknowledged_at"] = stamp(at)
        tries.mark(connection, continuation_id, attempt, {"acknowledged_at": stamp(at)})
        state.log(connection, "continuation_changed", step["page_id"], "Delivery acknowledged")
    cont.update(connection, continuation_id, changes)


def fail(
    connection: sqlite3.Connection,
    continuation_id: str,
    attempt: int,
    error: dict[str, Any],
    at: datetime,
) -> None:
    """The worker gives this attempt back; retried while attempts and the error allow."""
    validate("Error", error)
    step = current(connection, continuation_id, attempt, at)
    give_back(connection, step, at, error, "failed")


def complete(connection: sqlite3.Connection, step: dict[str, Any], at: datetime) -> None:
    """Its result was applied. The attempt's own acknowledgement stays on the record."""
    changes = {
        "state": "completed",
        "claimed_by": None,
        "lease_expires_at": None,
        "last_error": None,
        "updated_at": stamp(at),
    }
    cont.update(connection, step["id"], changes)
    ended = {"ended_at": stamp(at), "ended": "completed"}
    tries.mark(connection, step["id"], step["attempts"], ended)
    state.log(connection, "continuation_changed", step["page_id"], "Delivery completed")


def finish_runner(connection: sqlite3.Connection, run: runner.Run, at: datetime) -> None:
    """The runner's evidence is in: complete the delivery it held and release its job token."""
    step = None if run.continuation_id is None else cont.get(connection, run.continuation_id)
    if step is not None:
        complete(connection, step, at)
    runner.end(connection, run.page_id)
