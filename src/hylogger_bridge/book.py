# Purpose: persist live book pages, evidence and immutable decision history for a local demo.
import json
import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.provider import FixtureProvider, Provider
from hylogger_bridge.clock import moment, now, stamp
from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.events import ack, runner
from hylogger_bridge.events import claim as leases
from hylogger_bridge.events.fence import fence
from hylogger_bridge.pages import assess as advice_ops
from hylogger_bridge.pages.decide import decide as commit_decision
from hylogger_bridge.pages.finish import finish, merged
from hylogger_bridge.pages.make import new_page
from hylogger_bridge.science import live
from hylogger_bridge.science.describe import describe
from hylogger_bridge.science.request import KINDS, STAGES
from hylogger_bridge.store import cont, legacy, measures, scenes, state, tables, tries
from hylogger_bridge.store.conn import transaction

__all__ = ["BookConflict", "BookStore", "new_page", "now"]

EVIDENCE_FIELDS = {"id", "label", "value", "source", "kind"}
EVIDENCE_OPTIONAL = {"origin", "state"}


class BookStore:
    def __init__(
        self,
        path: Path,
        provider: Provider | None = None,
        science: live.Loader | None = None,
        start: dict[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.provider: Provider = provider or FixtureProvider()
        # Reads a TSG package for pages attached to one; pytsg loads only when one is attached.
        self.science: live.Loader = science or live.default_loader
        self.changed = threading.Condition()
        self._runs: dict[str, runner.Run] = {}
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy.upgrade(path)
        with transaction(path, self.changed) as connection:
            tables.create(connection)
            existing = connection.execute("SELECT data FROM book WHERE id=1").fetchone()
            if existing is not None and start is not None:
                if json.loads(existing[0])["run_id"] != start["run_id"]:
                    raise ValueError("this database already holds a different case")
            if existing is None:
                page = start["page"] if start else new_page(1)
                book = {
                    "run_id": start["run_id"] if start else "demo",
                    "source": start["source"] if start else "synthetic_demo",
                    "current_page_id": page["id"],
                    "pages": [page],
                }
                connection.execute("INSERT INTO book VALUES (1, ?)", (json.dumps(book),))
                made = "Real case created" if start else "Synthetic case created"
                state.save(connection, book, "page_created", page["id"], made)
            state.seal(connection)

    def snapshot(self) -> dict[str, Any]:
        with transaction(self.path, self.changed) as connection:
            return state.snapshot(connection)

    def events_after(self, sequence: int) -> list[dict[str, Any]]:
        if type(sequence) is not int or sequence < 0:
            raise ValueError("event cursor must be a nonnegative integer")
        with transaction(self.path, self.changed) as connection:
            return state.events(connection, sequence)

    def recover_interrupted(self, at: datetime | None = None) -> None:
        """Called once on service startup; opening another reader never cancels a job.

        Nothing the synthetic runner held survives a restart, and any lease that lapsed while the
        service was down is returned for retry.
        """
        moment_at = at or moment()
        with transaction(self.path, self.changed) as connection:
            leases.release_runner(connection, moment_at)
            leases.expire(connection, moment_at)
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
            connection.execute("DELETE FROM runners")
            state.seal(connection)
        self._runs.clear()

    def add_evidence(
        self,
        page_id: str,
        expected_revision: int,
        evidence: dict[str, object],
        claim: dict[str, Any] | None = None,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        """Incremental evidence. On a page that follows a delivery it needs the current claim.

        Old payloads have five fields and read as unspecified origin, complete. A worker may
        state origin and state itself; what it states is kept and validated, never replaced.
        """
        if (
            not EVIDENCE_FIELDS <= set(evidence) <= EVIDENCE_FIELDS | EVIDENCE_OPTIONAL
            or any(
                not isinstance(value, str) or not value.strip() or len(value) > 4000
                for value in evidence.values()
            )
            or evidence["kind"] not in ("observation", "calculation", "limitation")
        ):
            raise ValueError("evidence requires bounded text id, label, value, source and kind")
        stored = {"origin": "unspecified", "state": "complete", **evidence}
        validate("Evidence", stored)
        with transaction(self.path, self.changed) as connection:
            self._store_evidence(connection, page_id, expected_revision, stored, claim, at)
            state.seal(connection)
            return state.snapshot(connection)

    def _store_evidence(
        self,
        connection: sqlite3.Connection,
        page_id: str,
        expected_revision: int,
        stored: dict[str, object],
        claim: dict[str, Any] | None,
        at: datetime | None,
    ) -> None:
        book = state.read(connection)
        page = state.find(book, page_id, expected_revision)
        if page["status"] != "draft":
            raise BookConflict("Only the working draft can receive evidence", "page_locked")
        fence(connection, page, claim, at or moment())
        if any(item["id"] == stored["id"] for item in page["evidence"]):
            raise BookConflict("Evidence ID already exists", "invalid_request")
        page["evidence"] = merged(page, [stored], None)
        state.replace(book, page)
        state.save(connection, book, "evidence_added", page_id, str(stored["label"]))

    def begin_demo(
        self, page_id: str, expected_revision: int, at: datetime | None = None
    ) -> runner.Run:
        """Start the staged runner and return the exact run its callback must present."""
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
            # The synthetic runner is a built-in worker: it takes the delivery like any other.
            held = leases.adopt(connection, page, at or moment())
            connection.execute("INSERT OR REPLACE INTO jobs VALUES (?, 'running')", (page_id,))
            run = runner.begin(connection, page_id, held)
            page["progress"] = "Running synthetic example"
            page["demo_running"] = True
            state.replace(book, page)
            state.save(connection, book, "demo_started", page_id, "Synthetic runner started")
            state.seal(connection)
        self._runs[page_id] = run
        return run

    def start_demo(self, page_id: str, expected_revision: int, at: datetime | None = None) -> bool:
        self.begin_demo(page_id, expected_revision, at)
        return True

    def run_demo(
        self,
        page_id: str,
        delay: float = 0.7,
        run: runner.Run | None = None,
        clock: Callable[[], datetime] = moment,
    ) -> None:
        """Stage the synthetic evidence. A callback that no longer owns its run changes nothing."""
        run = run or self._runs.get(page_id)
        if run is None:
            return
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
                if not runner.valid(connection, run, clock()):
                    return
                book = state.read(connection)
                page = next(p for p in book["pages"] if p["id"] == page_id)
                if page["status"] != "draft":
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
            when = clock()
            if not runner.valid(connection, run, when):
                return
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
            ack.finish_runner(connection, run, when)
            state.save(connection, book, "page_ready", page_id, "Synthetic evidence ready")
            state.seal(connection)
        if self._runs.get(page_id) == run:
            del self._runs[page_id]

    def decide(
        self, page_id: str, expected_revision: int, choice: str, note: str, request_id: str
    ) -> dict[str, Any]:
        with transaction(self.path, self.changed) as connection:
            commit_decision(connection, page_id, expected_revision, choice, note, request_id)
            state.seal(connection)
            return state.snapshot(connection)

    def claim_delivery(
        self, worker: str, seconds: float = leases.SECONDS, at: datetime | None = None
    ) -> dict[str, Any] | None:
        """Hand the oldest pending delivery to a worker as a Handoff, or None."""
        with transaction(self.path, self.changed) as connection:
            handoff = leases.claim(connection, worker, at or moment(), seconds)
            state.seal(connection)
            return handoff

    def acknowledge_delivery(
        self,
        continuation_id: str,
        attempt: int,
        seconds: float = leases.SECONDS,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        with transaction(self.path, self.changed) as connection:
            ack.acknowledge(connection, continuation_id, attempt, at or moment(), seconds)
            state.seal(connection)
            return state.snapshot(connection)

    def fail_delivery(
        self,
        continuation_id: str,
        attempt: int,
        error: dict[str, Any],
        at: datetime | None = None,
    ) -> dict[str, Any]:
        with transaction(self.path, self.changed) as connection:
            ack.fail(connection, continuation_id, attempt, error, at or moment())
            state.seal(connection)
            return state.snapshot(connection)

    def expire_deliveries(self, at: datetime | None = None) -> int:
        """Return every claim whose lease ended; claims also expire when anyone next acts."""
        with transaction(self.path, self.changed) as connection:
            count = leases.expire(connection, at or moment())
            state.seal(connection)
            return count

    def submit_result(
        self, completion: dict[str, Any], at: datetime | None = None
    ) -> dict[str, Any]:
        """Apply one worker result to the working page: complete, partial or failed."""
        with transaction(self.path, self.changed) as connection:
            finish(connection, completion, at or moment())
            state.seal(connection)
            return state.snapshot(connection)

    def request_assessment(
        self,
        page_id: str,
        expected_revision: int,
        candidates: list[dict[str, Any]] | None = None,
        instruction: str = "",
        at: datetime | None = None,
    ) -> dict[str, Any]:
        """Ask the provider for advice. Inference runs outside any database transaction.

        The request is prepared in one short transaction and the advice recorded in another that
        re-checks the page, so a slow provider never blocks other operations and advice for a
        page that changed meanwhile is refused rather than stored as current.
        """
        asked = at or moment()
        with transaction(self.path, self.changed) as connection:
            request, token = advice_ops.prepare(
                connection, page_id, expected_revision, candidates, instruction
            )
        advice = self.provider.assess(request, stamp(asked))
        with transaction(self.path, self.changed) as connection:
            advice_ops.record(connection, request, advice, token)
            state.seal(connection)
            return state.snapshot(connection)

    def attempts(self, continuation_id: str) -> list[dict[str, Any]]:
        with transaction(self.path, self.changed) as connection:
            if cont.get(connection, continuation_id) is None:
                raise BookConflict("Unknown delivery", "not_found")
            return tries.history(connection, continuation_id)

    def attach_scene(
        self,
        page_id: str,
        expected_revision: int,
        folder: Path,
        package_id: str,
        target: tuple[float, float],
        reference: tuple[float, float],
        question: str | None = None,
        claim: dict[str, Any] | None = None,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        """Tie a working page to a TSG package and two intervals. A trusted local call only.

        The package is read and its identity checked outside any writer transaction; its file
        hashes are recorded. A scene is attached once and counts a page revision. Repeating the
        identical call changes nothing; a different scene or question needs a new page. It is
        deliberately not an HTTP or MCP operation.
        """
        if question is not None and (
            not isinstance(question, str) or not 0 < len(question.strip()) <= 300
        ):
            raise ValueError("question must be bounded text")
        with transaction(self.path, self.changed) as connection:
            page = self._draft(connection, page_id, expected_revision)
            fence(connection, page, claim, at or moment())
        scene = live.attach(self.science, str(folder), package_id, target, reference)
        with transaction(self.path, self.changed) as connection:
            book = state.read(connection)
            page = self._draft(connection, page_id, expected_revision)
            fence(connection, page, claim, at or moment())
            fresh = scenes.put(connection, page_id, scene)
            if not fresh and question in (None, page["question"]):
                state.seal(connection)
                return state.snapshot(connection)
            if not fresh:
                raise BookConflict("This page already has its question and scene", "request_reuse")
            if question is not None:
                page["question"] = question
            state.replace(book, page)
            # Reported as evidence_added: the shared Event contract has no scene event, and
            # changing that contract is not part of this work.
            state.save(connection, book, "evidence_added", page_id, "Scientific scene attached")
            state.seal(connection)
            return state.snapshot(connection)

    def _draft(
        self, connection: sqlite3.Connection, page_id: str, expected_revision: int
    ) -> dict[str, Any]:
        page = state.find(state.read(connection), page_id, expected_revision)
        if page["status"] != "draft":
            raise BookConflict("Only the working draft can be changed", "page_locked")
        return page

    def measure(
        self,
        page_id: str,
        expected_revision: int,
        stage: str,
        claim: dict[str, Any] | None = None,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        """Persist one calculated evidence item with its features; the values are never supplied.

        The package is read and calculated outside any writer transaction. The commit then
        stores the evidence and its measurement together, only if the page revision, the claim
        and the scene are still what the calculation used.
        """
        if stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}")
        with transaction(self.path, self.changed) as connection:
            self._draft(connection, page_id, expected_revision)
            scene = scenes.get(connection, page_id)
        if scene is None:
            raise ValueError("this page has no scientific scene")
        hole = live.hole_of(self.science, scene)
        values = live.known(self.science, scene)[stage]
        label, value = describe(
            hole,
            (float(scene["target"][0]), float(scene["target"][1])),
            (float(scene["reference"][0]), float(scene["reference"][1])),
            stage,
            values,
        )
        item: dict[str, object] = {
            "id": stage,
            "label": label,
            "value": value,
            "source": f"{scene['hole_id']} via pytsg; {scene['method']}",
            "kind": KINDS[stage],
            "origin": "actual",
            "state": "complete",
        }
        validate("Evidence", item)
        with transaction(self.path, self.changed) as connection:
            if scenes.get(connection, page_id) != scene:
                raise BookConflict(
                    "The page's scene changed during the calculation", "stale_revision"
                )
            self._store_evidence(connection, page_id, expected_revision, item, claim, at)
            measures.put(connection, page_id, item, dict(values))
            state.seal(connection)
            return state.snapshot(connection)
