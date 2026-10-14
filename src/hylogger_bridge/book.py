# Purpose: persist live book pages, evidence and immutable decision history for a local demo.
import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class BookConflict(ValueError):
    """A stale request or immutable page prevents a requested mutation."""


def now() -> str:
    return datetime.now(UTC).isoformat()


def new_page(number: int, parent_id: str | None = None) -> dict[str, Any]:
    timestamp = now()
    return {
        "id": str(uuid.uuid4()),
        "number": number,
        "parent_id": parent_id,
        "template": "investigation" if number == 1 else "candidate_evidence",
        "template_version": 1,
        "title": "An unfamiliar drill hole" if number == 1 else "Follow-up investigation",
        "question": "Show spectral-change intervals that overlap assay records.",
        "status": "draft",
        "revision": 0,
        "summary": "A synthetic case for exploring the live investigation book.",
        "progress": "Ready to start the synthetic example",
        "evidence": [],
        "decision": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "scientific_review": "unreviewed",
        "demo_running": False,
    }


class BookStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.changed = threading.Condition()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS book (id INTEGER PRIMARY KEY, data TEXT)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                "data TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS jobs (page_id TEXT PRIMARY KEY, status TEXT NOT NULL)"
            )
            if connection.execute("SELECT id FROM book WHERE id=1").fetchone() is None:
                page = new_page(1)
                book = {
                    "run_id": "demo",
                    "source": "synthetic_demo",
                    "current_page_id": page["id"],
                    "pages": [page],
                }
                connection.execute("INSERT INTO book VALUES (1, ?)", (json.dumps(book),))
                self._write(connection, book, "page_created", page["id"], "Synthetic case created")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
            if connection.total_changes:
                with self.changed:
                    self.changed.notify_all()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _book(connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute("SELECT data FROM book WHERE id=1").fetchone()
        if row is None:
            raise ValueError("book is not initialised")
        value: dict[str, Any] = json.loads(row[0])
        return value

    @staticmethod
    def _page(book: dict[str, Any], page_id: str, revision: int) -> dict[str, Any]:
        if type(revision) is not int or revision < 0:
            raise ValueError("expected_revision must be a nonnegative integer")
        for page in book["pages"]:
            if page["id"] == page_id:
                if page["status"] == "locked" or page["revision"] != revision:
                    raise BookConflict("Page changed or is locked; refresh before continuing")
                return dict(page)
        raise ValueError("unknown page")

    @staticmethod
    def _replace(book: dict[str, Any], page: dict[str, Any]) -> None:
        page["revision"] += 1
        page["updated_at"] = now()
        book["pages"] = [page if item["id"] == page["id"] else item for item in book["pages"]]

    @staticmethod
    def _write(
        connection: sqlite3.Connection,
        book: dict[str, Any],
        event_type: str,
        page_id: str,
        detail: str,
    ) -> None:
        connection.execute("UPDATE book SET data=? WHERE id=1", (json.dumps(book),))
        event = {"type": event_type, "page_id": page_id, "at": now(), "detail": detail}
        connection.execute("INSERT INTO events(data) VALUES (?)", (json.dumps(event),))

    @staticmethod
    def _events(connection: sqlite3.Connection, after: int) -> list[dict[str, Any]]:
        return [
            {"sequence": row[0], **json.loads(row[1])}
            for row in connection.execute(
                "SELECT sequence,data FROM events WHERE sequence>? ORDER BY sequence", (after,)
            )
        ]

    def _snapshot(self, connection: sqlite3.Connection) -> dict[str, Any]:
        book = self._book(connection)
        for page in book["pages"]:
            page.setdefault("demo_running", False)
        sequence = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
        return {
            **book,
            "sequence": sequence,
            "events": self._events(connection, max(0, sequence - 20)),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._transaction() as connection:
            return self._snapshot(connection)

    def events_after(self, sequence: int) -> list[dict[str, Any]]:
        if type(sequence) is not int or sequence < 0:
            raise ValueError("event cursor must be a nonnegative integer")
        with self._transaction() as connection:
            return self._events(connection, sequence)

    def recover_interrupted(self) -> None:
        """Called once on service startup; opening another reader never cancels a job."""
        with self._transaction() as connection:
            book = self._book(connection)
            interrupted = connection.execute(
                "SELECT page_id FROM jobs WHERE status='running'"
            ).fetchall()
            for (page_id,) in interrupted:
                page = next(p for p in book["pages"] if p["id"] == page_id)
                if page["status"] == "draft":
                    page["demo_running"] = False
                    page["progress"] = "Example interrupted; start again to continue"
                    self._replace(book, page)
                    self._write(connection, book, "demo_interrupted", page_id, "Service restarted")
            connection.execute("UPDATE jobs SET status='interrupted' WHERE status='running'")

    def add_evidence(
        self, page_id: str, expected_revision: int, evidence: dict[str, object]
    ) -> dict[str, Any]:
        required = {"id", "label", "value", "source", "kind"}
        if (
            set(evidence) != required
            or any(
                not isinstance(value, str) or not value.strip() or len(value) > 4000
                for value in evidence.values()
            )
            or evidence["kind"] not in ("observation", "calculation", "limitation")
        ):
            raise ValueError("evidence requires bounded text id, label, value, source and kind")
        with self._transaction() as connection:
            book = self._book(connection)
            page = self._page(book, page_id, expected_revision)
            if page["status"] != "draft":
                raise BookConflict("Only the working draft can receive evidence")
            if any(item["id"] == evidence["id"] for item in page["evidence"]):
                raise BookConflict("Evidence ID already exists")
            page["evidence"].append(evidence)
            self._replace(book, page)
            self._write(connection, book, "evidence_added", page_id, str(evidence["label"]))
            return self._snapshot(connection)

    def start_demo(self, page_id: str, expected_revision: int) -> bool:
        with self._transaction() as connection:
            book = self._book(connection)
            page = self._page(book, page_id, expected_revision)
            if page["status"] != "draft":
                raise BookConflict("Only a draft can start the example")
            job = connection.execute(
                "SELECT status FROM jobs WHERE page_id=?", (page_id,)
            ).fetchone()
            if job is not None and job[0] != "interrupted":
                raise BookConflict("This page already has a demo run")
            connection.execute("INSERT OR REPLACE INTO jobs VALUES (?, 'running')", (page_id,))
            page["progress"] = "Running synthetic example"
            page["demo_running"] = True
            self._replace(book, page)
            self._write(connection, book, "demo_started", page_id, "Synthetic runner started")
        return True

    def run_demo(self, page_id: str, delay: float = 0.7) -> None:
        candidate, assay = (214.0, 220.0), (215.0, 218.0)
        overlap = max(0.0, min(candidate[1], assay[1]) - max(candidate[0], assay[0]))
        steps = [
            (
                "qa",
                "Quality check",
                "Synthetic depth coverage and linkage checks passed",
                "observation",
            ),
            (
                "candidate",
                "Candidate interval",
                "214–220 m · fabricated persistent spectral change",
                "observation",
            ),
            (
                "assay",
                "Assay record",
                "215–218 m · fabricated assay coverage; no grade inference",
                "observation",
            ),
            (
                "overlap",
                "Depth overlap",
                f"{overlap:g} m / {candidate[1] - candidate[0]:g} m = "
                f"{100 * overlap / (candidate[1] - candidate[0]):g}% candidate coverage",
                "calculation",
            ),
            (
                "limit",
                "Review boundary",
                "Synthetic example only. Geological meaning remains unreviewed.",
                "limitation",
            ),
        ]
        for item_id, label, value, kind in steps:
            time.sleep(delay)
            with self._transaction() as connection:
                book = self._book(connection)
                page = next(p for p in book["pages"] if p["id"] == page_id)
                job = connection.execute(
                    "SELECT status FROM jobs WHERE page_id=?", (page_id,)
                ).fetchone()
                if page["status"] != "draft" or job is None or job[0] != "running":
                    return
                # Restarting an interrupted demonstration never duplicates existing evidence.
                evidence_id = f"synthetic-{item_id}"
                if any(e["id"] == evidence_id for e in page["evidence"]):
                    continue
                page["evidence"].append(
                    {
                        "id": evidence_id,
                        "label": label,
                        "value": value,
                        "kind": kind,
                        "source": "Built-in synthetic fixture v1",
                    }
                )
                page["progress"] = label
                self._replace(book, page)
                self._write(connection, book, "evidence_added", page_id, label)
        with self._transaction() as connection:
            book = self._book(connection)
            page = next(p for p in book["pages"] if p["id"] == page_id)
            if page["status"] != "draft":
                return
            page["status"] = "ready"
            page["demo_running"] = False
            page["progress"] = "Evidence ready for your workflow decision"
            page["summary"] = (
                "The synthetic 214–220 m candidate overlaps an assay record by 3 m (50%)."
            )
            self._replace(book, page)
            connection.execute("UPDATE jobs SET status='done' WHERE page_id=?", (page_id,))
            self._write(connection, book, "page_ready", page_id, "Synthetic evidence ready")

    def decide(
        self, page_id: str, expected_revision: int, choice: str, note: str, request_id: str
    ) -> dict[str, Any]:
        if choice not in ("accept", "modify", "reject"):
            raise ValueError("unsupported workflow decision")
        if not isinstance(note, str) or len(note) > 4000:
            raise ValueError("note must be text of at most 4000 characters")
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 200:
            raise ValueError("request_id is required and bounded")
        payload = json.dumps([page_id, expected_revision, choice, note])
        with self._transaction() as connection:
            previous = connection.execute(
                "SELECT payload FROM requests WHERE id=?", (request_id,)
            ).fetchone()
            if previous:
                if previous[0] != payload:
                    raise BookConflict("Request ID was already used for a different decision")
                return self._snapshot(connection)
            book = self._book(connection)
            page = self._page(book, page_id, expected_revision)
            if page["status"] != "ready":
                raise BookConflict("Evidence must be ready before a decision is recorded")
            page["decision"] = {"choice": choice, "note": note, "recorded_at": now()}
            page["status"] = "locked"
            self._replace(book, page)
            successor = new_page(page["number"] + 1, page_id)
            successor["summary"] = f"Previous workflow choice: {choice}. " + (
                note or "Choose the next evidence to examine."
            )
            book["pages"].append(successor)
            book["current_page_id"] = successor["id"]
            connection.execute("INSERT INTO requests VALUES (?,?)", (request_id, payload))
            self._write(
                connection,
                book,
                "decision_recorded",
                page_id,
                "User workflow choice recorded; page locked and successor created",
            )
            return self._snapshot(connection)
