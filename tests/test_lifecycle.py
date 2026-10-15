# Purpose: prove atomic decisions, their delivery records, safe migration and error codes.
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from unittest import mock

from hylogger_bridge.book import BookConflict, BookStore
from hylogger_bridge.book_server import BookServer
from hylogger_bridge.contracts.book import check_book
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.store import cont
from hylogger_bridge.store.conn import transaction
from hylogger_bridge.store.legacy import SYNTHETIC
from hylogger_bridge.store.tables import UnsupportedVersion

SRC = Path(__file__).resolve().parents[1] / "src"
NOTE = "  Exact note – with é and a\nnewline  "


def working(snapshot: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = next(
        item for item in snapshot["pages"] if item["id"] == snapshot["current_page_id"]
    )
    return page


def ready(store: BookStore) -> dict[str, Any]:
    page = working(store.snapshot())
    store.start_demo(page["id"], page["revision"])
    store.run_demo(page["id"], delay=0)
    return working(store.snapshot())


class BookCase(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "book.sqlite3"

    def decide(self, store: BookStore, page: dict[str, Any], request_id: str = "r1") -> Any:
        return store.decide(page["id"], page["revision"], "modify", NOTE, request_id)


class DecisionTests(BookCase):
    def test_one_commit_locks_the_page_creates_the_successor_and_queues_delivery(self) -> None:
        store = BookStore(self.path)
        page = ready(store)
        snapshot = self.decide(store, page)
        check_book(snapshot)
        locked = next(item for item in snapshot["pages"] if item["id"] == page["id"])
        decision = locked["decision"]
        self.assertEqual((decision["choice"], decision["note"]), ("modify", NOTE))
        self.assertEqual(decision["actor"], {"kind": "human"})
        self.assertEqual(decision["locked_revision"], locked["revision"])
        self.assertEqual(decision["evidence_ids"], [item["id"] for item in page["evidence"]])
        (step,) = snapshot["continuations"]
        self.assertEqual(step["state"], "pending")
        self.assertEqual((step["attempts"], step["max_attempts"]), (0, cont.MAX_ATTEMPTS))
        self.assertEqual(step["decision_id"], decision["id"])
        self.assertEqual(step["successor_id"], snapshot["current_page_id"])

    def test_every_snapshot_of_the_demo_satisfies_the_contract(self) -> None:
        store = BookStore(self.path)
        check_book(store.snapshot())
        page = working(store.snapshot())
        store.start_demo(page["id"], page["revision"])
        check_book(store.snapshot())
        store.run_demo(page["id"], delay=0)
        prepared = working(store.snapshot())
        self.assertEqual(prepared["outcome"], "complete")
        self.assertEqual({item["origin"] for item in prepared["evidence"]}, {"synthetic"})
        check_book(store.snapshot())
        check_book(self.decide(store, prepared))

    def test_replaying_a_request_creates_nothing_new(self) -> None:
        store = BookStore(self.path)
        page = ready(store)
        first = self.decide(store, page)
        self.assertEqual(self.decide(store, page), first)
        self.assertEqual(len(first["pages"]), 2)
        self.assertEqual(len(first["continuations"]), 1)

    def test_conflicts_say_why(self) -> None:
        store = BookStore(self.path)
        draft = working(store.snapshot())
        with self.assertRaises(BookConflict) as early:
            self.decide(store, draft)
        self.assertEqual(early.exception.code, "not_ready")
        page = ready(store)
        with self.assertRaises(BookConflict) as stale:
            store.decide(page["id"], page["revision"] - 1, "accept", "", "s1")
        self.assertEqual(stale.exception.code, "stale_revision")
        self.decide(store, page)
        with self.assertRaises(BookConflict) as locked:
            self.decide(store, page, "r2")
        self.assertEqual(locked.exception.code, "page_locked")
        with self.assertRaises(BookConflict) as reuse:
            store.decide(page["id"], page["revision"], "reject", NOTE, "r1")
        self.assertEqual(reuse.exception.code, "request_reuse")

    def test_a_failure_part_way_leaves_nothing_behind(self) -> None:
        store = BookStore(self.path)
        page = ready(store)
        before = store.snapshot()
        with mock.patch.object(cont, "insert", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                self.decide(store, page)
        self.assertEqual(store.snapshot(), before)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 0)
        after = self.decide(store, page)
        self.assertEqual(len(after["continuations"]), 1)
        self.assertEqual(len(after["pages"]), 2)

    def test_browsers_are_told_only_after_a_commit(self) -> None:
        store = BookStore(self.path)
        page = ready(store)
        with mock.patch.object(store.changed, "notify_all") as notify:
            with mock.patch.object(cont, "insert", side_effect=RuntimeError("disk full")):
                with self.assertRaises(RuntimeError):
                    self.decide(store, page)
            self.assertEqual(notify.call_count, 0)
            self.decide(store, page)
            self.assertGreaterEqual(notify.call_count, 1)

    def test_the_database_refuses_a_second_continuation_for_a_page(self) -> None:
        store = BookStore(self.path)
        page = ready(store)
        snapshot = self.decide(store, page)
        duplicate = {**snapshot["continuations"][0], "id": "another", "decision_id": "other"}
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.path, store.changed) as connection:
                cont.insert(connection, duplicate)
        self.assertEqual(len(store.snapshot()["continuations"]), 1)

    def test_competing_decisions_on_separate_connections_queue_one_delivery(self) -> None:
        first, second = BookStore(self.path), BookStore(self.path)
        page = ready(first)

        def attempt(index: int) -> str:
            try:
                self.decide(first if index == 0 else second, page, f"racer-{index}")
            except BookConflict:
                return "conflict"
            return "committed"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(attempt, range(2)))
        self.assertEqual(outcomes, ["committed", "conflict"])
        snapshot = first.snapshot()
        check_book(snapshot)
        self.assertEqual(len(snapshot["continuations"]), 1)
        self.assertEqual(len(snapshot["pages"]), 2)

    def test_delivery_record_survives_a_restart(self) -> None:
        store = BookStore(self.path)
        committed = self.decide(store, ready(store))
        reopened = BookStore(self.path)
        self.assertEqual(reopened.snapshot(), committed)
        check_book(reopened.snapshot())


def write_legacy(
    path: Path,
    *,
    with_successor: bool = True,
    edit: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """A version-0 book exactly as the first demo stored it."""
    stamp = "2026-10-14T09:00:00+00:00"

    def page(number: int, parent: str | None, status: str, revision: int) -> dict[str, Any]:
        return {
            "id": f"p{number}",
            "number": number,
            "parent_id": parent,
            "template": "investigation" if number == 1 else "candidate_evidence",
            "template_version": 1,
            "title": "An unfamiliar drill hole",
            "question": "Show spectral-change intervals that overlap assay records.",
            "status": status,
            "revision": revision,
            "summary": "A synthetic case.",
            "progress": "Evidence ready for your workflow decision",
            "evidence": [],
            "decision": None,
            "created_at": stamp,
            "updated_at": stamp,
            "scientific_review": "unreviewed",
        }

    first = page(1, None, "locked", 7)
    first["evidence"] = [
        {
            "id": "synthetic-qa",
            "label": "QA",
            "value": "ok",
            "source": SYNTHETIC,
            "kind": "observation",
        },
        {
            "id": "typed-1",
            "label": "Note",
            "value": "x",
            "source": "A test",
            "kind": "observation",
        },
    ]
    first["decision"] = {"choice": "modify", "note": "Test note", "recorded_at": stamp}
    pages = [first, page(2, "p1", "draft", 0)] if with_successor else [first]
    book = {
        "run_id": "demo",
        "source": "synthetic_demo",
        "current_page_id": pages[-1]["id"],
        "pages": pages,
    }
    if edit is not None:
        edit(book)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, data TEXT)")
        connection.execute(
            "CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)"
        )
        connection.execute("CREATE TABLE requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        connection.execute("CREATE TABLE jobs (page_id TEXT PRIMARY KEY, status TEXT NOT NULL)")
        connection.execute("INSERT INTO book VALUES (1, ?)", (json.dumps(book),))
        for kind in ("page_created", "decision_recorded"):
            event = {"type": kind, "page_id": "p1", "at": stamp, "detail": "Earlier"}
            connection.execute("INSERT INTO events(data) VALUES (?)", (json.dumps(event),))
        payload = json.dumps(["p1", 6, "modify", "Test note"])
        connection.execute("INSERT INTO requests VALUES ('req-old', ?)", (payload,))
    return book


def version(path: Path) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


class MigrationTests(BookCase):
    def test_old_history_is_kept_and_never_attributed_to_a_person(self) -> None:
        original = write_legacy(self.path)
        store = BookStore(self.path)
        snapshot = store.snapshot()
        check_book(snapshot)
        first, second = snapshot["pages"]
        self.assertEqual(first["decision"]["actor"], {"kind": "unknown"})
        self.assertEqual(first["decision"]["request_id"], "req-old")
        self.assertEqual(first["decision"]["note"], "Test note")
        self.assertEqual(first["decision"]["successor_id"], second["id"])
        self.assertEqual(first["outcome"], "complete")
        self.assertEqual([e["origin"] for e in first["evidence"]], ["synthetic", "unspecified"])
        self.assertEqual(snapshot["current_page_id"], second["id"])
        self.assertEqual(len(snapshot["events"]), 2)
        self.assertEqual(version(self.path), 1)
        backup = self.path.with_name(self.path.name + ".pre-v1.bak")
        with sqlite3.connect(backup) as old:
            self.assertEqual(old.execute("PRAGMA user_version").fetchone()[0], 0)
            stored = json.loads(old.execute("SELECT data FROM book").fetchone()[0])
            self.assertEqual(stored, original)

    def test_historical_decisions_are_never_dispatched(self) -> None:
        write_legacy(self.path)
        store = BookStore(self.path)
        self.assertEqual(store.snapshot()["continuations"], [])
        with self.assertRaises(BookConflict) as locked:
            store.decide("p1", 7, "accept", "", "again")
        self.assertEqual(locked.exception.code, "page_locked")
        page = ready(store)
        committed = self.decide(store, page)
        check_book(committed)
        self.assertEqual([step["page_id"] for step in committed["continuations"]], ["p2"])
        self.assertEqual(committed["pages"][1]["decision"]["actor"], {"kind": "human"})

    def test_reopening_neither_upgrades_again_nor_replaces_the_backup(self) -> None:
        write_legacy(self.path)
        first = BookStore(self.path).snapshot()
        backup = self.path.with_name(self.path.name + ".pre-v1.bak")
        kept = backup.read_bytes()
        self.assertEqual(BookStore(self.path).snapshot(), first)
        self.assertEqual(backup.read_bytes(), kept)

    def test_an_inconsistent_old_book_is_refused_and_left_untouched(self) -> None:
        original = write_legacy(self.path, with_successor=False)
        with self.assertRaises(ValueError):
            BookStore(self.path)
        self.assertEqual(version(self.path), 0)
        with sqlite3.connect(self.path) as connection:
            stored = json.loads(connection.execute("SELECT data FROM book").fetchone()[0])
        self.assertEqual(stored, original)

    def test_opening_together_upgrades_exactly_once(self) -> None:
        write_legacy(self.path)
        barrier = threading.Barrier(2)

        def open_book(_: int) -> dict[str, Any]:
            barrier.wait()
            return BookStore(self.path).snapshot()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(open_book, range(2))
        self.assertEqual(first, second)
        check_book(first)
        self.assertEqual(version(self.path), 1)

    def test_a_new_book_starts_at_the_current_version_without_a_backup(self) -> None:
        BookStore(self.path)
        self.assertEqual(version(self.path), 1)
        self.assertFalse(self.path.with_name(self.path.name + ".pre-v1.bak").exists())


class RefusedMigrationTests(BookCase):
    def refused(self, edit: Callable[[dict[str, Any]], None]) -> None:
        write_legacy(self.path, edit=edit)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            BookStore(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(version(self.path), 0)
        self.assertEqual(list(self.path.parent.glob("*.bak*")), [])

    def test_a_missing_current_page_is_refused_unchanged(self) -> None:
        self.refused(lambda book: book.update(current_page_id="missing"))

    def test_broken_numbering_is_refused_unchanged(self) -> None:
        self.refused(lambda book: book["pages"][1].update(number=5))

    def test_duplicate_identities_are_refused_unchanged(self) -> None:
        self.refused(lambda book: book["pages"][1].update(id="p1"))

    def test_invalid_evidence_is_refused_unchanged(self) -> None:
        self.refused(lambda book: book["pages"][0]["evidence"][1].update(id="bad id"))

    def test_a_decision_without_a_successor_is_refused_unchanged(self) -> None:
        write_legacy(self.path, with_successor=False)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            BookStore(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_migration_finishes_in_a_fresh_process_within_a_bound(self) -> None:
        write_legacy(self.path)
        code = (
            "import sys; from pathlib import Path; from hylogger_bridge.book import BookStore; "
            "BookStore(Path(sys.argv[1]))"
        )
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        done = subprocess.run(
            [sys.executable, "-c", code, str(self.path)],
            env=env,
            timeout=30,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(version(self.path), 1)
        self.assertTrue(self.path.with_name(self.path.name + ".pre-v1.bak").exists())


class VersionTests(BookCase):
    def test_a_newer_database_is_refused_and_left_unchanged(self) -> None:
        BookStore(self.path)
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA user_version = 2")
        before = self.path.read_bytes()
        with self.assertRaises(UnsupportedVersion):
            BookStore(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(version(self.path), 2)

    def test_a_negative_version_is_refused_too(self) -> None:
        BookStore(self.path)
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA user_version = -1")
        with self.assertRaises(UnsupportedVersion):
            BookStore(self.path)
        self.assertEqual(version(self.path), -1)


def item(name: str, **changes: str) -> dict[str, object]:
    base: dict[str, object] = {
        "id": name,
        "label": "Label",
        "value": "Value",
        "source": "Test fixture",
        "kind": "observation",
    }
    return {**base, **changes}


class BoundaryTests(BookCase):
    def test_a_maximum_note_is_kept_exactly_and_its_summary_is_bounded(self) -> None:
        store = BookStore(self.path)
        page = ready(store)
        note = ("né\n" * 1333) + "!"
        self.assertEqual(len(note), 4000)
        snapshot = store.decide(page["id"], page["revision"], "accept", note, "big")
        check_book(snapshot)
        locked = next(p for p in snapshot["pages"] if p["id"] == page["id"])
        self.assertEqual(locked["decision"]["note"], note)
        self.assertLessEqual(len(working(snapshot)["summary"]), 400)

    def test_an_over_long_note_is_refused_without_a_trace(self) -> None:
        store = BookStore(self.path)
        page = ready(store)
        before = store.snapshot()
        with self.assertRaises(ValueError):
            store.decide(page["id"], page["revision"], "accept", "x" * 4001, "long")
        self.assertEqual(store.snapshot(), before)

    def test_invalid_decision_requests_are_refused_without_a_trace(self) -> None:
        store = BookStore(self.path)
        page = ready(store)
        before = store.snapshot()
        bad: list[tuple[Any, Any, Any, Any]] = [
            (page["revision"], "approve", "", "r1"),
            (True, "accept", "", "r2"),
            (-1, "accept", "", "r3"),
            (page["revision"], "accept", None, "r4"),
            (page["revision"], "accept", "", ""),
            (page["revision"], "accept", "", "r" * 201),
        ]
        for revision, choice, note, request_id in bad:
            with self.subTest(choice=choice, revision=revision, request_id=request_id[:3]):
                with self.assertRaises(ValueError):
                    store.decide(page["id"], revision, choice, note, request_id)
        self.assertEqual(store.snapshot(), before)

    def test_invalid_evidence_is_refused_without_a_trace(self) -> None:
        store = BookStore(self.path)
        page = working(store.snapshot())
        before = store.snapshot()
        bad = [
            item("e" * 129),
            item("bad id"),
            item("ok", value="v" * 4001),
            item("ok", label=" "),
            item("ok", kind="approval"),
        ]
        for evidence in bad:
            with self.subTest(evidence=str(evidence["id"])[:12]):
                with self.assertRaises(ValueError):
                    store.add_evidence(page["id"], page["revision"], evidence)
        self.assertEqual(store.snapshot(), before)

    def test_a_page_holds_at_most_two_hundred_evidence_items(self) -> None:
        store = BookStore(self.path)
        for number in range(200):
            page = working(store.snapshot())
            store.add_evidence(page["id"], page["revision"], item(f"e{number}"))
        before = store.snapshot()
        check_book(before)
        page = working(before)
        with self.assertRaises(ValueError):
            store.add_evidence(page["id"], page["revision"], item("one-too-many"))
        self.assertEqual(store.snapshot(), before)


class HttpTests(BookCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = BookStore(self.path)
        self.server = BookServer(0, self.store, self.path.parent)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.stop)

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload

    def test_snapshot_and_decision_follow_the_contract_and_errors_carry_codes(self) -> None:
        status, snapshot = self.call("GET", "/api/book")
        self.assertEqual(status, 200)
        check_book(snapshot)
        page = ready(self.store)
        url = f"/api/pages/{page['id']}/decision"
        body = {"choice": "accept", "note": NOTE, "expected_revision": page["revision"]}
        status, committed = self.call("POST", url, {**body, "request_id": "http-1"})
        self.assertEqual(status, 200)
        check_book(committed)
        self.assertEqual(len(committed["continuations"]), 1)
        self.assertEqual(self.call("POST", url, {**body, "request_id": "http-1"}), (200, committed))
        status, error = self.call("POST", url, {**body, "request_id": "http-2"})
        self.assertEqual(status, 409)
        validate("Error", error)
        self.assertEqual(error["code"], "page_locked")
        status, error = self.call("POST", url, {"choice": "approve"})
        self.assertEqual(status, 400)
        validate("Error", error)
        self.assertEqual(error["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
