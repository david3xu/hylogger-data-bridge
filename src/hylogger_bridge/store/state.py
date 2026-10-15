# Purpose: read and write the book document and its event log inside a caller-owned transaction.
import json
import sqlite3
from typing import Any

from hylogger_bridge.clock import now
from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.book import check_book
from hylogger_bridge.store import cont

CONTRACT_VERSION = 1


def read(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute("SELECT data FROM book WHERE id=1").fetchone()
    if row is None:
        raise ValueError("book is not initialised")
    value: dict[str, Any] = json.loads(row[0])
    return value


def find(book: dict[str, Any], page_id: str, revision: int) -> dict[str, Any]:
    """Return a copy of a working page the caller may change, or say why it may not."""
    if type(revision) is not int or revision < 0:
        raise ValueError("expected_revision must be a nonnegative integer")
    message = "Page changed or is locked; refresh before continuing"
    for page in book["pages"]:
        if page["id"] == page_id:
            if page["status"] == "locked":
                raise BookConflict(message, "page_locked")
            if page["revision"] != revision:
                raise BookConflict(message, "stale_revision")
            return dict(page)
    raise ValueError("unknown page")


def put(book: dict[str, Any], page: dict[str, Any]) -> None:
    """Store a page without counting a revision: for advisory metadata only."""
    book["pages"] = [page if item["id"] == page["id"] else item for item in book["pages"]]


def replace(book: dict[str, Any], page: dict[str, Any]) -> None:
    page["revision"] += 1
    page["updated_at"] = now()
    put(book, page)


def log(connection: sqlite3.Connection, event_type: str, page_id: str, detail: str) -> None:
    event = {"type": event_type, "page_id": page_id, "at": now(), "detail": detail}
    connection.execute("INSERT INTO events(data) VALUES (?)", (json.dumps(event),))


def save(
    connection: sqlite3.Connection,
    book: dict[str, Any],
    event_type: str,
    page_id: str,
    detail: str,
) -> None:
    connection.execute("UPDATE book SET data=? WHERE id=1", (json.dumps(book),))
    log(connection, event_type, page_id, detail)


def events(connection: sqlite3.Connection, after: int) -> list[dict[str, Any]]:
    return [
        {"sequence": row[0], **json.loads(row[1])}
        for row in connection.execute(
            "SELECT sequence,data FROM events WHERE sequence>? ORDER BY sequence", (after,)
        )
    ]


def project(
    book: dict[str, Any],
    continuations: list[dict[str, Any]],
    sequence: int,
    recent: list[dict[str, Any]],
) -> dict[str, Any]:
    """The contract Book: pages are immutable once locked; delivery state is separate."""
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": book["run_id"],
        "source": book["source"],
        "current_page_id": book["current_page_id"],
        "pages": book["pages"],
        "continuations": continuations,
        "sequence": sequence,
        "events": recent,
    }


def latest(connection: sqlite3.Connection) -> tuple[int, list[dict[str, Any]]]:
    sequence = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
    return int(sequence), events(connection, max(0, sequence - 20))


def snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    sequence, recent = latest(connection)
    return project(read(connection), cont.rows(connection), sequence, recent)


def seal(connection: sqlite3.Connection) -> None:
    """Refuse to commit a book that breaks the shared contract."""
    check_book(snapshot(connection))
