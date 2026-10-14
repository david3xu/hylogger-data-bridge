# Purpose: persist live book pages, evidence and immutable decision history for a local demo.
import json
import threading
import time
from pathlib import Path
from typing import Any

from hylogger_bridge.clock import now
from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.pages.decide import decide as commit_decision
from hylogger_bridge.pages.make import new_page
from hylogger_bridge.store import legacy, state, tables
from hylogger_bridge.store.conn import transaction

__all__ = ["BookConflict", "BookStore", "new_page", "now"]

EVIDENCE_FIELDS = {"id", "label", "value", "source", "kind"}
MAX_EVIDENCE = 200


class BookStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.changed = threading.Condition()
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy.upgrade(path)
        with transaction(path, self.changed) as connection:
            tables.create(connection)
            if connection.execute("SELECT id FROM book WHERE id=1").fetchone() is None:
                page = new_page(1)
                book = {
                    "run_id": "demo",
                    "source": "synthetic_demo",
                    "current_page_id": page["id"],
                    "pages": [page],
                }
                connection.execute("INSERT INTO book VALUES (1, ?)", (json.dumps(book),))
                state.save(connection, book, "page_created", page["id"], "Synthetic case created")
            state.seal(connection)

    def snapshot(self) -> dict[str, Any]:
        with transaction(self.path, self.changed) as connection:
            return state.snapshot(connection)

    def events_after(self, sequence: int) -> list[dict[str, Any]]:
        if type(sequence) is not int or sequence < 0:
            raise ValueError("event cursor must be a nonnegative integer")
        with transaction(self.path, self.changed) as connection:
            return state.events(connection, sequence)

    def recover_interrupted(self) -> None:
        """Called once on service startup; opening another reader never cancels a job."""
        with transaction(self.path, self.changed) as connection:
            book = state.read(connection)
            interrupted = connection.execute(
                "SELECT page_id FROM jobs WHERE status='running'"
            ).fetchall()
            for (page_id,) in interrupted:
                page = next(p for p in book["pages"] if p["id"] == page_id)
                if page["status"] == "draft":
                    page["demo_running"] = False
                    page["progress"] = "Example interrupted; start again to continue"
                    state.replace(book, page)
                    state.save(connection, book, "demo_interrupted", page_id, "Service restarted")
            connection.execute("UPDATE jobs SET status='interrupted' WHERE status='running'")
            state.seal(connection)

    def add_evidence(
        self, page_id: str, expected_revision: int, evidence: dict[str, object]
    ) -> dict[str, Any]:
        if (
            set(evidence) != EVIDENCE_FIELDS
            or any(
                not isinstance(value, str) or not value.strip() or len(value) > 4000
                for value in evidence.values()
            )
            or evidence["kind"] not in ("observation", "calculation", "limitation")
        ):
            raise ValueError("evidence requires bounded text id, label, value, source and kind")
        # This endpoint predates declared provenance, so the origin stays honestly unspecified.
        stored = {**evidence, "origin": "unspecified", "state": "complete"}
        validate("Evidence", stored)
        with transaction(self.path, self.changed) as connection:
            book = state.read(connection)
            page = state.find(book, page_id, expected_revision)
            if page["status"] != "draft":
                raise BookConflict("Only the working draft can receive evidence", "page_locked")
            if any(item["id"] == evidence["id"] for item in page["evidence"]):
                raise BookConflict("Evidence ID already exists", "invalid_request")
            if len(page["evidence"]) >= MAX_EVIDENCE:
                raise ValueError(f"a page holds at most {MAX_EVIDENCE} evidence items")
            page["evidence"] = [*page["evidence"], stored]
            state.replace(book, page)
            state.save(connection, book, "evidence_added", page_id, str(evidence["label"]))
            state.seal(connection)
            return state.snapshot(connection)

    def start_demo(self, page_id: str, expected_revision: int) -> bool:
        with transaction(self.path, self.changed) as connection:
            book = state.read(connection)
            page = state.find(book, page_id, expected_revision)
            if page["status"] != "draft":
                raise BookConflict("Only a draft can start the example", "page_locked")
            job = connection.execute(
                "SELECT status FROM jobs WHERE page_id=?", (page_id,)
            ).fetchone()
            if job is not None and job[0] != "interrupted":
                raise BookConflict("This page already has a demo run", "request_reuse")
            connection.execute("INSERT OR REPLACE INTO jobs VALUES (?, 'running')", (page_id,))
            page["progress"] = "Running synthetic example"
            page["demo_running"] = True
            state.replace(book, page)
            state.save(connection, book, "demo_started", page_id, "Synthetic runner started")
            state.seal(connection)
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
            with transaction(self.path, self.changed) as connection:
                book = state.read(connection)
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
                        "origin": "synthetic",
                        "state": "complete",
                    }
                )
                page["progress"] = label
                state.replace(book, page)
                state.save(connection, book, "evidence_added", page_id, label)
                state.seal(connection)
        with transaction(self.path, self.changed) as connection:
            book = state.read(connection)
            page = next(p for p in book["pages"] if p["id"] == page_id)
            if page["status"] != "draft":
                return
            page["status"] = "ready"
            page["outcome"] = "complete"
            page["demo_running"] = False
            page["progress"] = "Evidence ready for your workflow decision"
            page["summary"] = (
                "The synthetic 214–220 m candidate overlaps an assay record by 3 m (50%)."
            )
            state.replace(book, page)
            connection.execute("UPDATE jobs SET status='done' WHERE page_id=?", (page_id,))
            state.save(connection, book, "page_ready", page_id, "Synthetic evidence ready")
            state.seal(connection)

    def decide(
        self, page_id: str, expected_revision: int, choice: str, note: str, request_id: str
    ) -> dict[str, Any]:
        with transaction(self.path, self.changed) as connection:
            commit_decision(connection, page_id, expected_revision, choice, note, request_id)
            state.seal(connection)
            return state.snapshot(connection)
