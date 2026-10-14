# Purpose: keep every delivery attempt, so one worker's receipt is never credited to another.
import sqlite3
from typing import Any

COLUMNS = (
    "continuation_id",
    "attempt",
    "worker",
    "claimed_at",
    "acknowledged_at",
    "ended_at",
    "ended",
)


def begin(
    connection: sqlite3.Connection, continuation_id: str, attempt: int, worker: str, at: str
) -> None:
    connection.execute(
        "INSERT INTO attempts (continuation_id, attempt, worker, claimed_at) VALUES (?,?,?,?)",
        (continuation_id, attempt, worker, at),
    )


def mark(
    connection: sqlite3.Connection, continuation_id: str, attempt: int, changes: dict[str, Any]
) -> None:
    if not set(changes) <= {"acknowledged_at", "ended_at", "ended"}:
        raise ValueError("unknown attempt column")
    sets = ",".join(f"{name}=?" for name in changes)
    connection.execute(
        f"UPDATE attempts SET {sets} WHERE continuation_id=? AND attempt=?",
        [*changes.values(), continuation_id, attempt],
    )


def history(connection: sqlite3.Connection, continuation_id: str) -> list[dict[str, Any]]:
    found = connection.execute(
        f"SELECT {','.join(COLUMNS)} FROM attempts WHERE continuation_id=? ORDER BY attempt",
        (continuation_id,),
    )
    return [dict(zip(COLUMNS, row, strict=True)) for row in found]
