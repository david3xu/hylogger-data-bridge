# Purpose: verify persisted book history, decision concurrency and worker write boundaries.
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from hylogger_bridge.book import BookConflict, BookStore

Snapshot = dict[str, object]


def pages(snapshot: Snapshot) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], snapshot["pages"])


def current(snapshot: Snapshot) -> dict[str, object]:
    return next(page for page in pages(snapshot) if page["id"] == snapshot["current_page_id"])


def revision(page: dict[str, object]) -> int:
    return cast(int, page["revision"])


def page_id(page: dict[str, object]) -> str:
    return cast(str, page["id"])


def evidence(item_id: str = "worker-observation") -> dict[str, object]:
    return {
        "id": item_id,
        "label": "Worker observation",
        "value": "Synthetic interval 214–220 m",
        "source": "Synthetic test fixture; no geological data",
        "kind": "observation",
    }


@pytest.fixture
def store(tmp_path: Path) -> BookStore:
    return BookStore(tmp_path / "book.sqlite3")


def ready(store: BookStore) -> dict[str, object]:
    initial = current(store.snapshot())
    assert store.start_demo(page_id(initial), revision(initial)) is True
    store.run_demo(page_id(initial), delay=0)
    page = current(store.snapshot())
    assert page["status"] == "ready"
    return page


def test_initial_book_is_saved_once_and_marks_science_unreviewed(tmp_path: Path) -> None:
    database = tmp_path / "book.sqlite3"
    first = BookStore(database).snapshot()
    second = BookStore(database).snapshot()
    assert first == second
    assert first["source"] == "synthetic_demo"
    assert len(pages(first)) == 1
    page = current(first)
    assert page["status"] == "draft"
    assert page["parent_id"] is None
    assert page["decision"] is None
    assert page["scientific_review"] == "unreviewed"


def test_worker_evidence_persists_and_emits_a_recoverable_event(store: BookStore) -> None:
    before = store.snapshot()
    draft = current(before)
    item = evidence()
    after = store.add_evidence(page_id(draft), revision(draft), item)
    assert item in cast(list[dict[str, object]], current(after)["evidence"])
    assert revision(current(after)) > revision(draft)
    changes = store.events_after(cast(int, before["sequence"]))
    assert any(event["type"] == "evidence_added" for event in changes)
    assert changes[-1]["sequence"] == after["sequence"]


def test_stale_worker_result_cannot_replace_new_evidence(store: BookStore) -> None:
    draft = current(store.snapshot())
    accepted = store.add_evidence(page_id(draft), revision(draft), evidence("first"))
    with pytest.raises(BookConflict):
        store.add_evidence(page_id(draft), revision(draft), evidence("stale"))
    assert store.snapshot() == accepted


@pytest.mark.parametrize("defect", ["missing_source", "unknown_kind", "forged_review"])
def test_invalid_worker_payload_never_mutates_the_book(store: BookStore, defect: str) -> None:
    before = store.snapshot()
    draft = current(before)
    payload = evidence()
    if defect == "missing_source":
        del payload["source"]
    elif defect == "unknown_kind":
        payload["kind"] = "geological_approval"
    else:
        payload["scientific_review"] = "approved"
    with pytest.raises(ValueError):
        store.add_evidence(page_id(draft), revision(draft), payload)
    assert store.snapshot() == before


@pytest.mark.parametrize("choice", ["accept", "modify", "reject"])
def test_decision_locks_evidence_and_creates_exactly_one_linked_draft(
    store: BookStore, choice: str
) -> None:
    prepared = ready(store)
    result = store.decide(page_id(prepared), revision(prepared), choice, "Actual choice", "r1")
    assert len(pages(result)) == 2
    locked = next(page for page in pages(result) if page["id"] == prepared["id"])
    successor = current(result)
    assert locked["status"] == "locked"
    assert locked["evidence"] == prepared["evidence"]
    assert locked["summary"] == prepared["summary"]
    decision = cast(dict[str, object], locked["decision"])
    assert decision["choice"] == choice
    assert decision["note"] == "Actual choice"
    assert decision["recorded_at"]
    assert successor["id"] != locked["id"]
    assert successor["parent_id"] == locked["id"]
    assert successor["number"] == cast(int, locked["number"]) + 1
    assert successor["status"] == "draft"
    assert successor["template"] == "candidate_evidence"
    assert successor["decision"] is None
    assert all(page["scientific_review"] == "unreviewed" for page in pages(result))

    frozen = deepcopy(locked)
    updated = store.add_evidence(page_id(successor), revision(successor), evidence("new-page"))
    assert next(page for page in pages(updated) if page["id"] == locked["id"]) == frozen


def test_retry_of_original_decision_is_idempotent_even_after_revision_changes(
    store: BookStore,
) -> None:
    prepared = ready(store)
    arguments = (page_id(prepared), revision(prepared), "modify", "Inspect adjacent interval", "r1")
    first = store.decide(*arguments)
    replay = store.decide(*arguments)
    assert replay == first
    decisions = [event for event in store.events_after(0) if event["type"] == "decision_recorded"]
    assert len(decisions) == 1
    assert len(pages(replay)) == 2


@pytest.mark.parametrize("changed", ["choice", "note", "revision"])
def test_request_id_cannot_be_reused_for_a_different_decision(
    store: BookStore, changed: str
) -> None:
    prepared = ready(store)
    original = store.decide(page_id(prepared), revision(prepared), "accept", "Review", "r1")
    with pytest.raises(BookConflict):
        store.decide(
            page_id(prepared),
            revision(prepared) + (1 if changed == "revision" else 0),
            "reject" if changed == "choice" else "accept",
            "Changed" if changed == "note" else "Review",
            "r1",
        )
    assert store.snapshot() == original


def test_decision_requires_ready_state_and_current_revision(store: BookStore) -> None:
    draft = current(store.snapshot())
    with pytest.raises(BookConflict):
        store.decide(page_id(draft), revision(draft), "accept", "Premature", "early")
    prepared = ready(store)
    with pytest.raises(BookConflict):
        store.decide(page_id(prepared), revision(draft), "accept", "Stale", "stale")
    assert current(store.snapshot()) == prepared


def test_ready_and_locked_pages_reject_worker_mutation(store: BookStore) -> None:
    prepared = ready(store)
    with pytest.raises(BookConflict):
        store.add_evidence(page_id(prepared), revision(prepared), evidence("late"))
    committed = store.decide(page_id(prepared), revision(prepared), "accept", "Keep", "r1")
    locked = next(page for page in pages(committed) if page["id"] == prepared["id"])
    with pytest.raises(BookConflict):
        store.add_evidence(page_id(locked), revision(locked), evidence("locked"))
    with pytest.raises(BookConflict):
        store.decide(page_id(locked), revision(locked), "reject", "Overwrite", "r2")
    assert store.snapshot() == committed


def test_reload_preserves_history_and_idempotency(tmp_path: Path) -> None:
    database = tmp_path / "book.sqlite3"
    original = BookStore(database)
    prepared = ready(original)
    arguments = (page_id(prepared), revision(prepared), "reject", "Needs evidence", "r1")
    committed = original.decide(*arguments)
    reopened = BookStore(database)
    assert reopened.snapshot() == committed
    assert reopened.decide(*arguments) == committed
    assert reopened.events_after(0) == original.events_after(0)


def test_event_sequence_supports_reconnect_without_duplicates(store: BookStore) -> None:
    checkpoint = cast(int, store.snapshot()["sequence"])
    prepared = ready(store)
    final = store.decide(page_id(prepared), revision(prepared), "accept", "Proceed", "r1")
    all_events = store.events_after(0)
    sequences = [cast(int, event["sequence"]) for event in all_events]
    assert sequences == sorted(set(sequences))
    assert sequences[-1] == final["sequence"]
    resumed = store.events_after(checkpoint)
    assert resumed == [event for event in all_events if cast(int, event["sequence"]) > checkpoint]
    assert store.events_after(cast(int, final["sequence"])) == []
    assert {event["type"] for event in resumed} >= {
        "demo_started",
        "evidence_added",
        "page_ready",
        "decision_recorded",
    }


def test_duplicate_demo_start_never_runs_another_worker(store: BookStore) -> None:
    draft = current(store.snapshot())
    assert store.start_demo(page_id(draft), revision(draft)) is True
    running = store.snapshot()
    with pytest.raises(BookConflict):
        store.start_demo(page_id(draft), revision(current(running)))
    assert store.snapshot() == running
    store.run_demo(page_id(draft), delay=0)
    prepared = current(store.snapshot())
    with pytest.raises(BookConflict):
        store.start_demo(page_id(prepared), revision(prepared))


def test_opening_a_second_store_does_not_interrupt_an_active_worker(tmp_path: Path) -> None:
    database = tmp_path / "book.sqlite3"
    worker = BookStore(database)
    draft = current(worker.snapshot())
    worker.start_demo(page_id(draft), revision(draft))
    observer = BookStore(database)
    worker.run_demo(page_id(draft), delay=0)
    assert current(observer.snapshot())["status"] == "ready"
    assert observer.snapshot() == worker.snapshot()


def test_explicit_startup_recovery_resumes_without_duplicating_evidence(store: BookStore) -> None:
    draft = current(store.snapshot())
    store.add_evidence(page_id(draft), revision(draft), evidence("synthetic-qa"))
    updated = current(store.snapshot())
    store.start_demo(page_id(updated), revision(updated))
    assert current(store.snapshot())["demo_running"] is True
    store.recover_interrupted()
    interrupted = current(store.snapshot())
    assert interrupted["demo_running"] is False
    assert interrupted["status"] == "draft"
    assert store.start_demo(page_id(interrupted), revision(interrupted)) is True
    store.run_demo(page_id(interrupted), delay=0)
    completed = current(store.snapshot())
    assert completed["status"] == "ready"
    assert completed["demo_running"] is False
    items = cast(list[dict[str, object]], completed["evidence"])
    assert len(items) == 5
    assert len({item["id"] for item in items}) == 5


def test_competing_decisions_on_separate_connections_create_one_successor(tmp_path: Path) -> None:
    database = tmp_path / "book.sqlite3"
    first = BookStore(database)
    second = BookStore(database)
    prepared = ready(first)

    def attempt(index: int) -> str:
        connection = first if index == 0 else second
        try:
            connection.decide(
                page_id(prepared), revision(prepared), "accept", "Proceed", f"concurrent-{index}"
            )
        except BookConflict:
            return "conflict"
        return "committed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert sorted(outcomes) == ["committed", "conflict"]
    snapshot = first.snapshot()
    assert len(pages(snapshot)) == 2
    assert len([page for page in pages(snapshot) if page["status"] == "locked"]) == 1
    assert first.snapshot() == second.snapshot()
