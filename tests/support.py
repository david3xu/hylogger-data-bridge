# Purpose: shared helpers for the delivery tests: a scratch book, a ready page, fixed times.
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.book import BookStore

T0 = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
SRC = Path(__file__).resolve().parents[1] / "src"
NOTE = "  Exact note – keep every space  "


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def working(snapshot: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = next(
        item for item in snapshot["pages"] if item["id"] == snapshot["current_page_id"]
    )
    return page


def page_of(snapshot: dict[str, Any], page_id: str) -> dict[str, Any]:
    page: dict[str, Any] = next(item for item in snapshot["pages"] if item["id"] == page_id)
    return page


def ready(store: BookStore) -> dict[str, Any]:
    page = working(store.snapshot())
    store.start_demo(page["id"], page["revision"])
    store.run_demo(page["id"], delay=0)
    return working(store.snapshot())


def decided(store: BookStore) -> tuple[dict[str, Any], dict[str, Any]]:
    """A human decision on the ready first page: the snapshot and the new working page."""
    page = ready(store)
    snapshot = store.decide(page["id"], page["revision"], "modify", NOTE, "decision-1")
    return snapshot, working(snapshot)


def claim_of(handoff: dict[str, Any]) -> dict[str, Any]:
    return {"continuation_id": handoff["continuation_id"], "attempt": handoff["attempt"]}


def completion(
    page: dict[str, Any],
    handoff: dict[str, Any] | None,
    request_id: str = "work-1",
    **changes: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "contract_version": 1,
        "request_id": request_id,
        "page_id": page["id"],
        "expected_revision": page["revision"],
        "claim": None if handoff is None else claim_of(handoff),
        "outcome": "complete",
        "summary": "Overlap computed for the assay interval.",
        "evidence": [
            {
                "id": "overlap-1",
                "label": "Depth overlap",
                "value": "3 m / 6 m = 50% candidate coverage",
                "source": "Synthetic example, not a real result",
                "kind": "calculation",
                "origin": "synthetic",
                "state": "complete",
            }
        ],
        "errors": [],
        "action": {"type": "overlap_check", "assessment_id": None},
        "worker": {"kind": "agent", "name": "test-worker"},
    }
    return {**base, **changes}


def count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class Counting:
    """A provider that counts calls, to prove a refused request never reaches inference."""

    def __init__(self) -> None:
        self.calls = 0

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        self.calls += 1
        return FixtureProvider().assess(request, at)


class BookCase(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "book.sqlite3"
        self.store = BookStore(self.path)

    def claim_and_ack(self, worker: str, when: float) -> dict[str, Any]:
        handoff = self.store.claim_delivery(worker, at=at(when))
        assert handoff is not None
        self.store.acknowledge_delivery(
            handoff["continuation_id"], handoff["attempt"], at=at(when + 1)
        )
        return handoff

    def step(self) -> dict[str, Any]:
        step: dict[str, Any] = self.store.snapshot()["continuations"][0]
        return step
