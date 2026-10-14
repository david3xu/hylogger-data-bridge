# Purpose: prove the synthetic runner obeys its fence and advice never decides or blocks.
import sqlite3
import threading
import unittest
from typing import Any

from support import BookCase, at, completion, decided, page_of, ready, working

from hylogger_bridge.advice.provider import FixtureProvider, UnavailableProvider
from hylogger_bridge.book import BookConflict, BookStore
from hylogger_bridge.contracts.book import check_book
from hylogger_bridge.events.runner import RUNNER

RETRY = {"error": "The agent could not start", "code": "delivery_failed", "retryable": True}


class RunnerTests(BookCase):
    def count(self, table: str, page_id: str) -> int:
        with sqlite3.connect(self.path) as connection:
            query = f"SELECT COUNT(*) FROM {table} WHERE page_id=?"
            return int(connection.execute(query, (page_id,)).fetchone()[0])

    def test_the_runner_takes_a_delivery_like_any_other_worker(self) -> None:
        _, successor = decided(self.store)
        run = self.store.begin_demo(successor["id"], successor["revision"], at=at(0))
        step = self.step()
        held = (step["state"], step["claimed_by"], step["attempts"])
        self.assertEqual(held, ("running", RUNNER, 1))
        self.assertIsNotNone(step["acknowledged_at"])
        self.assertIsNone(self.store.claim_delivery("worker-a", at=at(1)))
        self.store.run_demo(successor["id"], delay=0, run=run, clock=lambda: at(5))
        snapshot = self.store.snapshot()
        check_book(snapshot)
        self.assertEqual(page_of(snapshot, successor["id"])["status"], "ready")
        self.assertEqual(self.step()["state"], "completed")
        (attempt,) = self.store.attempts(step["id"])
        self.assertEqual((attempt["worker"], attempt["ended"]), (RUNNER, "completed"))

    def test_a_worker_holding_the_delivery_keeps_the_runner_out(self) -> None:
        _, successor = decided(self.store)
        self.claim_and_ack("worker-a", 0)
        before = self.store.snapshot()
        with self.assertRaises(BookConflict) as held:
            self.store.start_demo(successor["id"], successor["revision"], at=at(1))
        self.assertEqual(held.exception.code, "page_locked")
        self.assertEqual(self.store.snapshot(), before)

    def test_an_exhausted_delivery_is_never_adopted(self) -> None:
        _, successor = decided(self.store)
        for round_ in range(3):
            handoff = self.store.claim_delivery("worker-a", at=at(round_ * 100))
            assert handoff is not None
            self.store.fail_delivery(
                handoff["continuation_id"], round_ + 1, RETRY, at=at(round_ * 100 + 1)
            )
        self.assertEqual(self.step()["state"], "failed")
        before = self.store.snapshot()
        with self.assertRaises(BookConflict) as refused:
            self.store.start_demo(successor["id"], successor["revision"], at=at(500))
        self.assertEqual(refused.exception.code, "delivery_failed")
        self.store.run_demo(successor["id"], delay=0)
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(self.count("jobs", successor["id"]), 0)
        self.assertEqual(self.count("runners", successor["id"]), 0)
        self.assertEqual(self.step()["state"], "failed")

    def test_a_runner_replaced_after_its_lease_ended_cannot_write(self) -> None:
        _, successor = decided(self.store)
        run = self.store.begin_demo(successor["id"], successor["revision"], at=at(0))
        replacement = self.claim_and_ack("replacement-worker", 601)
        before = self.store.snapshot()
        self.store.run_demo(successor["id"], delay=0, run=run, clock=lambda: at(603))
        self.assertEqual(self.store.snapshot(), before)
        page = page_of(before, successor["id"])
        self.assertEqual((page["status"], page["evidence"]), ("draft", []))
        step = self.step()
        self.assertEqual((step["state"], step["claimed_by"]), ("running", "replacement-worker"))
        done = self.store.submit_result(completion(page, replacement), at=at(604))
        self.assertEqual(page_of(done, successor["id"])["status"], "ready")

    def test_an_old_callback_after_a_restart_changes_nothing(self) -> None:
        _, successor = decided(self.store)
        old = self.store.begin_demo(successor["id"], successor["revision"], at=at(0))
        reopened = BookStore(self.path)
        reopened.recover_interrupted(at(10))
        before = reopened.snapshot()
        self.assertEqual(self.step()["state"], "pending")
        self.store.run_demo(successor["id"], delay=0, run=old, clock=lambda: at(11))
        self.assertEqual(reopened.snapshot(), before)
        page = working(before)
        new = reopened.begin_demo(page["id"], page["revision"], at=at(12))
        self.assertEqual(self.step()["attempts"], 2)
        self.store.run_demo(successor["id"], delay=0, run=old, clock=lambda: at(13))
        self.assertEqual(working(reopened.snapshot())["evidence"], [])
        reopened.run_demo(page["id"], delay=0, run=new, clock=lambda: at(14))
        self.assertEqual(working(reopened.snapshot())["status"], "ready")
        self.assertEqual(self.step()["state"], "completed")

    def test_a_run_nobody_started_does_nothing(self) -> None:
        page = working(self.store.snapshot())
        before = self.store.snapshot()
        self.store.run_demo(page["id"], delay=0)
        self.assertEqual(self.store.snapshot(), before)

    def test_the_first_page_runner_is_fenced_by_its_job_token(self) -> None:
        page = working(self.store.snapshot())
        old = self.store.begin_demo(page["id"], page["revision"])
        self.store.recover_interrupted()
        before = self.store.snapshot()
        self.store.run_demo(page["id"], delay=0, run=old)
        self.assertEqual(self.store.snapshot(), before)


class SlowProvider:
    """Blocks inside inference until released, to prove no database lock is held meanwhile."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        self.started.set()
        self.release.wait(10)
        return FixtureProvider().assess(request, at)


class GatedProvider:
    """Blocks each ask, named by its instruction, until the test releases it."""

    def __init__(self, *names: str) -> None:
        self.started = {name: threading.Event() for name in names}
        self.release = {name: threading.Event() for name in names}

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        name = request["instruction"]
        self.started[name].set()
        self.release[name].wait(10)
        return FixtureProvider().assess(request, at)


class RogueProvider:
    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        advice = FixtureProvider().assess(request, at)
        advice["suggestions"][0]["candidate_id"] = "cand-invented"
        return advice


class AssessTests(BookCase):
    def item(self, name: str) -> dict[str, object]:
        return {
            "id": name,
            "label": "Note",
            "value": "Observed",
            "source": "Synthetic example",
            "kind": "observation",
        }

    def test_fixture_advice_is_labelled_recorded_and_not_a_revision(self) -> None:
        page = working(self.store.snapshot())
        snapshot = self.store.request_assessment(page["id"], page["revision"], at=at(0))
        check_book(snapshot)
        advised = working(snapshot)
        advice = advised["assessment"]
        self.assertEqual((advice["origin"], advice["model_version"]), ("fixture", "fixture-v1"))
        self.assertIn("no trained model was consulted", advice["limitations"][0])
        self.assertEqual(advised["revision"], page["revision"])
        after = self.store.add_evidence(page["id"], page["revision"], self.item("e1"))
        self.assertLess(advice["state_revision"], working(after)["revision"])

    def test_actions_do_not_follow_the_advice(self) -> None:
        _, successor = decided(self.store)
        handoff = self.claim_and_ack("worker-a", 0)
        snapshot = self.store.request_assessment(successor["id"], successor["revision"], at=at(2))
        advice = working(snapshot)["assessment"]
        top = min(advice["suggestions"], key=lambda item: item["rank"])
        self.assertNotEqual(top["candidate_id"], "cand-overlap_check")
        action = {"type": "overlap_check", "assessment_id": advice["id"]}
        result = completion(working(snapshot), handoff, action=action)
        done = self.store.submit_result(result, at=at(3))
        recorded = page_of(done, successor["id"])["action"]
        used = (recorded["type"], recorded["assessment_id"])
        self.assertEqual(used, ("overlap_check", advice["id"]))

    def test_action_validity_never_depends_on_advice(self) -> None:
        _, successor = decided(self.store)
        handoff = self.claim_and_ack("worker-a", 0)
        before = self.store.snapshot()
        bad = (
            {"type": "unlisted_action", "assessment_id": None},
            {"type": "overlap_check", "assessment_id": "assess-never-recorded"},
        )
        for action in bad:
            with self.assertRaises(ValueError):
                self.store.submit_result(completion(successor, handoff, action=action), at=at(2))
        self.assertEqual(self.store.snapshot(), before)
        declined = {"type": "stop", "assessment_id": None}
        done = self.store.submit_result(completion(successor, handoff, action=declined), at=at(3))
        self.assertEqual(page_of(done, successor["id"])["action"]["type"], "stop")

    def test_unavailable_advice_has_no_suggestions_and_work_continues(self) -> None:
        store = BookStore(self.path, provider=UnavailableProvider())
        page = working(store.snapshot())
        snapshot = store.request_assessment(page["id"], page["revision"], at=at(0))
        check_book(snapshot)
        advice = working(snapshot)["assessment"]
        self.assertEqual((advice["status"], advice["suggestions"]), ("unavailable", []))
        done = store.submit_result(completion(page, None), at=at(1))
        self.assertEqual(working(done)["status"], "ready")

    def test_a_custom_provider_is_checked_before_anything_is_recorded(self) -> None:
        store = BookStore(self.path, provider=RogueProvider())
        page = working(store.snapshot())
        before = store.snapshot()
        with self.assertRaises(ValueError):
            store.request_assessment(page["id"], page["revision"], at=at(0))
        self.assertEqual(store.snapshot(), before)

    def newer_ask_survives(self, first: dict[str, Any], second: dict[str, Any]) -> None:
        """Hold the older ask in inference, finish the newer one, then release the older."""
        gate = GatedProvider("old task", "new task")
        store = BookStore(self.path, provider=gate)
        page = working(store.snapshot())
        outcome: list[BaseException] = []

        def ask_old() -> None:
            try:
                store.request_assessment(page["id"], page["revision"], **first)
            except BaseException as error:
                outcome.append(error)

        thread = threading.Thread(target=ask_old)
        thread.start()
        self.assertTrue(gate.started["old task"].wait(10))
        gate.release["new task"].set()
        newest = working(store.request_assessment(page["id"], page["revision"], **second))
        gate.release["old task"].set()
        thread.join(10)
        self.assertFalse(thread.is_alive())
        (error,) = outcome
        assert isinstance(error, BookConflict)
        self.assertEqual(error.code, "stale_revision")
        kept = working(store.snapshot())
        self.assertEqual(kept["assessment"], newest["assessment"])
        self.assertEqual(kept["revision"], page["revision"])
        check_book(store.snapshot())

    def test_an_older_instruction_cannot_replace_newer_advice(self) -> None:
        self.newer_ask_survives({"instruction": "old task"}, {"instruction": "new task"})

    def test_older_candidates_cannot_replace_newer_advice(self) -> None:
        def only(name: str) -> list[dict[str, Any]]:
            return [{"id": f"cand-{name}", "action_type": name, "arguments": {}}]

        self.newer_ask_survives(
            {"instruction": "old task", "candidates": only("qa_check")},
            {"instruction": "new task", "candidates": only("stop")},
        )

    def test_sequential_asks_each_replace_the_last(self) -> None:
        page = working(self.store.snapshot())
        first = self.store.request_assessment(page["id"], page["revision"], instruction="one")
        second = self.store.request_assessment(page["id"], page["revision"], instruction="two")
        before = working(first)["assessment"]["id"]
        after = working(second)["assessment"]["id"]
        self.assertNotEqual(before, after)
        self.assertEqual(working(self.store.snapshot()), working(second))

    def test_inference_runs_outside_the_database_lock(self) -> None:
        slow = SlowProvider()
        store = BookStore(self.path, provider=slow)
        page = working(store.snapshot())
        outcome: list[BaseException] = []

        def ask() -> None:
            try:
                store.request_assessment(page["id"], page["revision"], at=at(0))
            except BaseException as error:
                outcome.append(error)

        thread = threading.Thread(target=ask)
        thread.start()
        self.assertTrue(slow.started.wait(10))
        other = BookStore(self.path)
        other.snapshot()
        other.add_evidence(page["id"], page["revision"], self.item("moved-on"))
        slow.release.set()
        thread.join(10)
        self.assertFalse(thread.is_alive())
        (error,) = outcome
        self.assertIsInstance(error, BookConflict)
        assert isinstance(error, BookConflict)
        self.assertEqual(error.code, "stale_revision")
        self.assertIsNone(working(store.snapshot())["assessment"])

    def test_advice_for_a_page_locked_meanwhile_is_refused(self) -> None:
        slow = SlowProvider()
        store = BookStore(self.path, provider=slow)
        page = ready(store)
        outcome: list[BaseException] = []

        def ask() -> None:
            try:
                store.request_assessment(page["id"], page["revision"], at=at(0))
            except BaseException as error:
                outcome.append(error)

        thread = threading.Thread(target=ask)
        thread.start()
        self.assertTrue(slow.started.wait(10))
        locked = store.decide(page["id"], page["revision"], "accept", "", "d1")
        frozen = page_of(locked, page["id"])
        slow.release.set()
        thread.join(10)
        (error,) = outcome
        assert isinstance(error, BookConflict)
        self.assertEqual(error.code, "page_locked")
        self.assertEqual(page_of(store.snapshot(), page["id"]), frozen)
        self.assertIsNone(frozen["assessment"])


if __name__ == "__main__":
    unittest.main()
