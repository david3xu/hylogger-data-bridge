# Purpose: read and write continuation (delivery) rows inside a caller-owned transaction.
import json
import sqlite3
from typing import Any

MAX_ATTEMPTS = 3
COLUMNS = (
    "id",
    "decision_id",
    "page_id",
    "successor_id",
    "locked_revision",
    "state",
    "attempts",
    "max_attempts",
    "claimed_by",
    "lease_expires_at",
    "acknowledged_at",
    "last_error",
    "created_at",
    "updated_at",
)
SELECT = f"SELECT {','.join(COLUMNS)} FROM continuations"


def _decode(row: tuple[Any, ...]) -> dict[str, Any]:
    record = dict(zip(COLUMNS, row, strict=True))
    record["last_error"] = json.loads(record["last_error"])
    return record


def insert(connection: sqlite3.Connection, record: dict[str, Any]) -> None:
    values = [record[name] for name in COLUMNS]
    values[COLUMNS.index("last_error")] = json.dumps(record["last_error"])
    marks = ",".join("?" * len(COLUMNS))
    connection.execute(f"INSERT INTO continuations ({','.join(COLUMNS)}) VALUES ({marks})", values)


def rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [_decode(row) for row in connection.execute(f"{SELECT} ORDER BY rowid")]


def get(connection: sqlite3.Connection, continuation_id: str) -> dict[str, Any] | None:
    row = connection.execute(f"{SELECT} WHERE id=?", (continuation_id,)).fetchone()
    return None if row is None else _decode(row)


def for_page(connection: sqlite3.Connection, page_id: str) -> dict[str, Any] | None:
    row = connection.execute(f"{SELECT} WHERE page_id=?", (page_id,)).fetchone()
    return None if row is None else _decode(row)


def in_state(connection: sqlite3.Connection, state: str) -> list[dict[str, Any]]:
    found = connection.execute(f"{SELECT} WHERE state=? ORDER BY rowid", (state,))
    return [_decode(row) for row in found]


def update(connection: sqlite3.Connection, continuation_id: str, changes: dict[str, Any]) -> None:
    if not set(changes) <= set(COLUMNS[1:]):
        raise ValueError("unknown continuation column")
    values = dict(changes)
    if "last_error" in values:
        values["last_error"] = json.dumps(values["last_error"])
    sets = ",".join(f"{name}=?" for name in values)
    connection.execute(
        f"UPDATE continuations SET {sets} WHERE id=?", [*values.values(), continuation_id]
    )
