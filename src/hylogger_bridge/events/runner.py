# Purpose: bind the staged synthetic runner to one job, one token and one delivery attempt.
import sqlite3
import uuid
from datetime import datetime
from typing import NamedTuple

from hylogger_bridge.clock import parse
from hylogger_bridge.store import cont, state

RUNNER = "synthetic-runner"


class Run(NamedTuple):
    """What a started demo must still own, at every write, for its callback to count."""

    page_id: str
    token: str
    continuation_id: str | None
    attempt: int | None


def begin(connection: sqlite3.Connection, page_id: str, held: tuple[str, int] | None) -> Run:
    continuation_id, attempt = held if held is not None else (None, None)
    run = Run(page_id, str(uuid.uuid4()), continuation_id, attempt)
    connection.execute("INSERT OR REPLACE INTO runners VALUES (?,?,?,?)", run)
    return run


def valid(connection: sqlite3.Connection, run: Run, at: datetime) -> bool:
    """Read-only: does this exact run still own its job and, if any, its unexpired attempt?"""
    owner = connection.execute("SELECT token FROM runners WHERE page_id=?", (run.page_id,))
    found = owner.fetchone()
    if found is None or found[0] != run.token:
        return False
    job = connection.execute("SELECT status FROM jobs WHERE page_id=?", (run.page_id,)).fetchone()
    if job is None or job[0] != "running":
        return False
    if run.continuation_id is None:
        return True
    step = cont.get(connection, run.continuation_id)
    return bool(
        step is not None
        and step["state"] == "running"
        and step["attempts"] == run.attempt
        and step["claimed_by"] == RUNNER
        and parse(step["lease_expires_at"]) > at
    )


def end(connection: sqlite3.Connection, page_id: str) -> None:
    connection.execute("DELETE FROM runners WHERE page_id=?", (page_id,))


def invalidate(connection: sqlite3.Connection, page_id: str) -> None:
    """The runner lost its delivery: stop its job and show the page as interrupted."""
    end(connection, page_id)
    connection.execute(
        "UPDATE jobs SET status='interrupted' WHERE page_id=? AND status='running'", (page_id,)
    )
    book = state.read(connection)
    page = next((p for p in book["pages"] if p["id"] == page_id), None)
    if page is not None and page["status"] == "draft" and page["demo_running"]:
        page["demo_running"] = False
        page["progress"] = "Example interrupted; start again to continue"
        state.replace(book, page)
        detail = "The synthetic runner lost its claim"
        state.save(connection, book, "demo_interrupted", page_id, detail)
