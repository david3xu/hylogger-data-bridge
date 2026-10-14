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


def insert(connection: sqlite3.Connection, record: dict[str, Any]) -> None:
    values = [record[name] for name in COLUMNS]
    values[COLUMNS.index("last_error")] = json.dumps(record["last_error"])
    marks = ",".join("?" * len(COLUMNS))
    connection.execute(f"INSERT INTO continuations ({','.join(COLUMNS)}) VALUES ({marks})", values)


def rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    found = connection.execute(f"SELECT {','.join(COLUMNS)} FROM continuations ORDER BY rowid")
    out = [dict(zip(COLUMNS, row, strict=True)) for row in found]
    for record in out:
        record["last_error"] = json.loads(record["last_error"])
    return out
