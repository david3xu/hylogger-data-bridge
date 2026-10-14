# Purpose: upgrade a version-0 book to the v1 contract without losing or relabelling history.
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from hylogger_bridge.contracts.book import check_book
from hylogger_bridge.store import state, tables

SYNTHETIC = "Built-in synthetic fixture v1"


def _evidence(item: dict[str, Any]) -> dict[str, Any]:
    # Only the demo runner wrote this exact source; any other origin was never recorded.
    origin = "synthetic" if item["source"] == SYNTHETIC else "unspecified"
    return {**item, "origin": origin, "state": "complete"}


def _decision(page: dict[str, Any], successor_id: str, request_id: str) -> dict[str, Any]:
    old = page["decision"]
    return {
        "id": f"legacy-{page['id']}",
        "page_id": page["id"],
        "choice": old["choice"],
        "note": old["note"],
        "request_id": request_id,
        "locked_revision": page["revision"],
        "successor_id": successor_id,
        "evidence_ids": [item["id"] for item in page["evidence"]],
        # Early decisions included automated tests; nothing proves a person made them.
        "actor": {"kind": "unknown"},
        "recorded_at": old["recorded_at"],
    }


def upgrade_book(book: dict[str, Any], requests: dict[str, str]) -> dict[str, Any]:
    """Add v1 fields in place. Old decisions are history: unknown actor, no continuation."""
    children = {page["parent_id"]: page["id"] for page in book["pages"] if page["parent_id"]}
    for page in book["pages"]:
        page["evidence"] = [_evidence(item) for item in page["evidence"]]
        page["outcome"] = None if page["status"] == "draft" else "complete"
        page["errors"] = []
        page["action"] = None
        page["assessment"] = None
        page.setdefault("demo_running", False)
        if page["decision"] is not None:
            if page["id"] not in children:
                raise ValueError(f"legacy page {page['id']} has a decision but no successor")
            request_id = requests.get(page["id"], "legacy")
            page["decision"] = _decision(page, children[page["id"]], request_id)
    return book


def _legacy(connection: sqlite3.Connection) -> bool:
    found = tables.require_supported(connection)
    has_book = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='book'"
    ).fetchone()
    return found == 0 and has_book is not None


def _upgraded(connection: sqlite3.Connection) -> dict[str, Any] | None:
    """The whole upgraded book, proven valid against the contract before anything is written."""
    row = connection.execute("SELECT data FROM book WHERE id=1").fetchone()
    if row is None:
        return None
    found = connection.execute("SELECT id, payload FROM requests")
    requests = {json.loads(payload)[0]: request_id for request_id, payload in found}
    book = upgrade_book(json.loads(row[0]), requests)
    sequence, recent = state.latest(connection)
    check_book(state.project(book, [], sequence, recent))
    return book


def _free(path: Path) -> Path:
    for number in range(100):
        suffix = ".pre-v1.bak" if number == 0 else f".pre-v1.{number}.bak"
        if not path.with_name(path.name + suffix).exists():
            return path.with_name(path.name + suffix)
    raise FileExistsError("too many earlier migration backups; remove some and retry")


def _backup(path: Path) -> Path:
    """Copy the old file through a separate read-only connection, never the writer.

    The migration holds only a reserved lock, which still lets this reader take a consistent
    snapshot, so the copy is bounded and shows exactly what is about to be replaced.
    """
    target = _free(path)
    partial = target.with_name(target.name + ".partial")
    source = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
    copy = sqlite3.connect(partial)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()
    os.replace(partial, target)
    return target


def upgrade(path: Path) -> None:
    """Upgrade once, atomically; a refusal or failure leaves the file exactly as it was."""
    if not path.exists():
        return
    connection = sqlite3.connect(path, timeout=10)
    made: Path | None = None
    try:
        if not _legacy(connection):
            return
        connection.execute("BEGIN IMMEDIATE")
        if _legacy(connection):  # the winner of a race upgrades; the loser finds version 1
            book = _upgraded(connection)
            made = _backup(path)
            if book is not None:
                connection.execute("UPDATE book SET data=? WHERE id=1", (json.dumps(book),))
            tables.create(connection)
        connection.commit()
    except BaseException:
        connection.rollback()
        if made is not None:
            made.unlink(missing_ok=True)
        raise
    finally:
        connection.close()
