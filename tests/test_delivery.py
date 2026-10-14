# Purpose: prove claims, acknowledgements, retries, fencing and idempotent results hold up.
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any
from unittest import mock

from support import (
    NOTE,
    BookCase,
    at,
    claim_of,
    completion,
    decided,
    page_of,
    working,
)

from hylogger_bridge.book import BookConflict, BookStore
from hylogger_bridge.contracts.book import check_book
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.store import tables, tries

RETRY = {"error": "The agent could not start", "code": "delivery_failed", "retryable": True}
FINAL = {**RETRY, "retryable": False}


class ClaimTests(BookCase):
    def test_decision_to_ready_with_immutable_history(self) -> None:
        snapshot, successor = decided(self.store)
        source = deepcopy(snapshot["pages"][0])
        handoff = self.store.claim_delivery("worker-a", at=at(0))
        assert handoff is not None
        validate("Handoff", handoff)
        kept = (handoff["choice"], handoff["note"], handoff["attempt"])
        self.assertEqual(kept, ("modify", NOTE, 1))
        self.assertEqual(handoff["actor"], {"kind": "human"})
        self.assertIsNone(self.step()["acknowledged_at"])
        self.store.acknowledge_delivery(handoff["continuation_id"], 1, at=at(1))
        after = self.store.submit_result(completion(successor, handoff), at=at(2))
        check_book(after)
        page = page_of(after, successor["id"])
        self.assertEqual((page["status"], page["outcome"]), ("ready", "complete"))
        self.assertEqual(page["action"]["actor"], {"kind": "agent", "name": "test-worker"})
        self.assertEqual(page_of(after, source["id"]), source)
        step = self.step()
        self.assertEqual(step["state"], "completed")
        self.assertIsNotNone(step["acknowledged_at"])
        (attempt,) = self.store.attempts(step["id"])
        self.assertEqual((attempt["worker"], attempt["ended"]), ("worker-a", "completed"))

    def test_a_new_attempt_never_inherits_the_previous_acknowledgement(self) -> None:
        _, successor = decided(self.store)
        first = self.claim_and_ack("worker-a", 0)
        second = self.store.claim_delivery("worker-b", at=at(100))
        assert second is not None
        self.assertEqual(second["attempt"], 2)
        step = self.step()
        self.assertEqual((step["claimed_by"], step["attempts"]), ("worker-b", 2))
        self.assertIsNone(step["acknowledged_at"])
        old, new = self.store.attempts(step["id"])
        self.assertIsNotNone(old["acknowledged_at"])
        self.assertEqual((old["worker"], old["ended"]), ("worker-a", "expired"))
        self.assertEqual((new["worker"], new["acknowledged_at"]), ("worker-b", None))
        with self.assertRaises(BookConflict) as unacknowledged:
            self.store.submit_result(completion(successor, second, "b-1"), at=at(101))
        self.assertEqual(unacknowledged.exception.code, "not_ready")
        with self.assertRaises(BookConflict) as late_ack:
            self.store.acknowledge_delivery(first["continuation_id"], 1, at=at(102))
        self.assertEqual(late_ack.exception.code, "claim_expired")
        self.store.acknowledge_delivery(second["continuation_id"], 2, at=at(103))
        self.store.submit_result(completion(successor, second, "b-2"), at=at(104))
        old, new = self.store.attempts(step["id"])
        self.assertNotEqual(old["acknowledged_at"], new["acknowledged_at"])
        self.assertEqual(self.step()["acknowledged_at"], new["acknowledged_at"])

    def test_expiry_before_acknowledgement_returns_the_delivery(self) -> None:
        decided(self.store)
        self.store.claim_delivery("worker-a", at=at(0))
        self.assertEqual(self.store.expire_deliveries(at(59)), 0)
        self.assertEqual(self.store.expire_deliveries(at(61)), 1)
        self.assertEqual(self.step()["state"], "pending")
        (attempt,) = self.store.attempts(self.step()["id"])
        self.assertEqual((attempt["acknowledged_at"], attempt["ended"]), (None, "expired"))
        retry = self.store.claim_delivery("worker-b", at=at(62))
        assert retry is not None
        self.assertEqual(retry["attempt"], 2)

    def test_acknowledgement_renews_the_lease(self) -> None:
        decided(self.store)
        handoff = self.store.claim_delivery("worker-a", at=at(0))
        assert handoff is not None
        self.store.acknowledge_delivery(handoff["continuation_id"], 1, at=at(50))
        self.assertEqual(self.store.expire_deliveries(at(100)), 0)
        self.assertEqual(self.store.expire_deliveries(at(111)), 1)

    def test_retries_are_bounded_and_exhaustion_is_terminal(self) -> None:
        _, successor = decided(self.store)
        for round_ in range(3):
            when = round_ * 100
            handoff = self.store.claim_delivery("worker-a", at=at(when))
            assert handoff is not None
            self.assertEqual(handoff["attempt"], round_ + 1)
            self.store.expire_deliveries(at(when + 61))
        step = self.step()
        self.assertEqual((step["state"], step["attempts"]), ("failed", 3))
        self.assertFalse(step["last_error"]["retryable"])
        self.assertIsNone(self.store.claim_delivery("worker-a", at=at(1000)))
        check_book(self.store.snapshot())
        self.assertEqual(working(self.store.snapshot())["id"], successor["id"])
        self.assertEqual(working(self.store.snapshot())["status"], "draft")
        self.assertEqual(len(self.store.attempts(step["id"])), 3)

    def test_a_worker_can_return_or_fail_its_attempt(self) -> None:
        decided(self.store)
        first = self.claim_and_ack("worker-a", 0)
        self.store.fail_delivery(first["continuation_id"], 1, RETRY, at=at(5))
        self.assertEqual(self.step()["state"], "pending")
        self.assertIsNone(self.step()["acknowledged_at"])
        second = self.store.claim_delivery("worker-b", at=at(6))
        assert second is not None
        self.store.fail_delivery(second["continuation_id"], 2, FINAL, at=at(7))
        step = self.step()
        self.assertEqual((step["state"], step["attempts"]), ("failed", 2))
        self.assertEqual(step["last_error"], FINAL)
        with self.assertRaises(BookConflict):
            self.store.fail_delivery(second["continuation_id"], 2, RETRY, at=at(8))

    def test_competing_claims_have_one_winner(self) -> None:
        decided(self.store)
        rival = BookStore(self.path)
        barrier = threading.Barrier(2)

        def attempt(index: int) -> Any:
            barrier.wait()
            worker = self.store if index == 0 else rival
            return worker.claim_delivery(f"worker-{index}", at=at(0))

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(item is not None for item in outcomes), 1)
        self.assertEqual(self.step()["attempts"], 1)

    def test_a_finished_delivery_is_not_delivered_again(self) -> None:
        _, successor = decided(self.store)
        handoff = self.claim_and_ack("worker-a", 0)
        self.store.submit_result(completion(successor, handoff), at=at(3))
        self.assertIsNone(self.store.claim_delivery("worker-b", at=at(4)))
        with self.assertRaises(BookConflict) as stale:
            self.store.acknowledge_delivery(handoff["continuation_id"], 1, at=at(5))
        self.assertEqual(stale.exception.code, "claim_expired")

    def test_restart_recovery_returns_a_lapsed_claim(self) -> None:
        decided(self.store)
        self.claim_and_ack("worker-a", 0)
        reopened = BookStore(self.path)
        self.assertEqual(reopened.snapshot()["continuations"][0]["state"], "running")
        reopened.recover_interrupted(at(120))
        self.assertEqual(reopened.snapshot()["continuations"][0]["state"], "pending")
        again = reopened.claim_delivery("worker-b", at=at(121))
        assert again is not None
        self.assertEqual(again["attempt"], 2)


class ResultTests(BookCase):
    def test_replays_are_harmless_and_reuse_is_a_conflict(self) -> None:
        _, successor = decided(self.store)
        handoff = self.claim_and_ack("worker-a", 0)
        result = completion(successor, handoff)
        first = self.store.submit_result(result, at=at(2))
        self.assertEqual(self.store.submit_result(result, at=at(3)), first)
        ready_events = [e for e in first["events"] if e["type"] == "page_ready"]
        self.assertEqual(len(ready_events), 2)  # the demo's first page, then this result
        changed = completion(successor, handoff, summary="A different summary.")
        with self.assertRaises(BookConflict) as reused:
            self.store.submit_result(changed, at=at(4))
        self.assertEqual(reused.exception.code, "request_reuse")
        other = completion(page_of(first, successor["id"]), handoff, "work-2")
        with self.assertRaises(BookConflict) as late:
            self.store.submit_result(other, at=at(5))
        self.assertEqual(late.exception.code, "not_ready")
        self.assertEqual(self.store.snapshot(), first)

    def test_stale_revisions_are_refused_without_a_trace(self) -> None:
        _, successor = decided(self.store)
        handoff = self.claim_and_ack("worker-a", 0)
        before = self.store.snapshot()
        for wrong in (successor["revision"] + 1, successor["revision"] + 5):
            with self.assertRaises(BookConflict) as stale:
                self.store.submit_result(completion(successor, handoff, expected_revision=wrong))
            self.assertEqual(stale.exception.code, "stale_revision")
        self.assertEqual(self.store.snapshot(), before)

    def test_unrelated_destinations_are_refused(self) -> None:
        snapshot, successor = decided(self.store)
        locked = snapshot["pages"][0]
        handoff = self.claim_and_ack("worker-a", 0)
        before = self.store.snapshot()
        elsewhere = completion(successor, handoff, "u2", page_id="nowhere")
        cases = {
            "locked history": (completion(locked, None, "u1"), "page_locked"),
            "unknown page": (elsewhere, "unrelated_page"),
            "no claim": (completion(successor, None, "u3"), "unrelated_page"),
            "another delivery": (
                completion(
                    successor,
                    handoff,
                    "u4",
                    claim={"continuation_id": "other-delivery", "attempt": 1},
                ),
                "unrelated_page",
            ),
        }
        for name, (result, code) in cases.items():
            with self.subTest(name):
                with self.assertRaises(BookConflict) as refused:
                    self.store.submit_result(result, at=at(2))
                self.assertEqual(refused.exception.code, code)
        self.assertEqual(self.store.snapshot(), before)

    def test_a_claim_on_a_page_without_a_delivery_is_refused(self) -> None:
        first = working(self.store.snapshot())
        forged = {"continuation_id": "made-up", "attempt": 1}
        with self.assertRaises(BookConflict) as refused:
            self.store.submit_result(completion(first, None, claim=forged), at=at(0))
        self.assertEqual(refused.exception.code, "unrelated_page")

    def test_a_delayed_result_from_a_replaced_worker_changes_nothing(self) -> None:
        _, successor = decided(self.store)
        slow = self.claim_and_ack("worker-a", 0)
        fast = self.claim_and_ack("worker-b", 100)
        before = self.store.snapshot()
        with self.assertRaises(BookConflict) as late:
            self.store.submit_result(completion(successor, slow, "slow"), at=at(102))
        self.assertEqual(late.exception.code, "claim_expired")
        self.assertEqual(self.store.snapshot(), before)
        done = self.store.submit_result(completion(successor, fast, "fast"), at=at(103))
        self.assertEqual(page_of(done, successor["id"])["status"], "ready")

    def test_a_result_after_its_lease_ended_is_refused(self) -> None:
        _, successor = decided(self.store)
        handoff = self.claim_and_ack("worker-a", 0)
        with self.assertRaises(BookConflict) as lapsed:
            self.store.submit_result(completion(successor, handoff), at=at(500))
        self.assertEqual(lapsed.exception.code, "claim_expired")
        # The refused write rolled back with its transaction; the lapse is applied on next touch.
        self.assertEqual(self.store.expire_deliveries(at(500)), 1)
        self.assertEqual(self.step()["state"], "pending")

    def test_partial_and_failed_outcomes_need_no_synthetic_runner(self) -> None:
        first = working(self.store.snapshot())
        note = {"error": "Assay interval 3 has no depth record", "code": "worker_failed"}
        partial = completion(
            first,
            None,
            outcome="partial",
            errors=[{**note, "retryable": False}],
            summary="Two of three intervals were checked.",
        )
        after = self.store.submit_result(partial, at=at(0))
        check_book(after)
        page = page_of(after, first["id"])
        self.assertEqual((page["status"], page["outcome"]), ("ready", "partial"))
        self.assertEqual(page["errors"][0]["error"], note["error"])

    def test_a_failed_outcome_is_ready_for_a_decision(self) -> None:
        first = working(self.store.snapshot())
        error = {"error": "Assay depths are missing", "code": "worker_failed", "retryable": True}
        failed = completion(first, None, outcome="failed", evidence=[], errors=[error])
        after = self.store.submit_result(failed, at=at(0))
        check_book(after)
        page = page_of(after, first["id"])
        shown = (page["status"], page["outcome"], page["evidence"])
        self.assertEqual(shown, ("ready", "failed", []))
        decision = self.store.decide(page["id"], page["revision"], "reject", "Needs depths", "d1")
        check_book(decision)

    def test_a_failed_result_is_never_notified_as_committed(self) -> None:
        first = working(self.store.snapshot())
        with mock.patch.object(self.store.changed, "notify_all") as notify:
            with self.assertRaises(BookConflict):
                self.store.submit_result(completion(first, None, expected_revision=99), at=at(0))
            self.assertEqual(notify.call_count, 0)
            self.store.submit_result(completion(first, None, "fresh"), at=at(1))
            self.assertGreaterEqual(notify.call_count, 1)


class EvidenceTests(BookCase):
    def item(self, name: str, **changes: str) -> dict[str, object]:
        base: dict[str, object] = {
            "id": name,
            "label": "Depth overlap",
            "value": "Computed for 2 of 3 intervals",
            "source": "Synthetic example, not a real result",
            "kind": "calculation",
        }
        return {**base, **changes}

    def stored(self, snapshot: dict[str, Any], name: str) -> dict[str, Any]:
        found: dict[str, Any] = next(e for e in working(snapshot)["evidence"] if e["id"] == name)
        return found

    def test_supplied_provenance_and_state_are_kept(self) -> None:
        page = working(self.store.snapshot())
        marked = self.item("e1", origin="synthetic", state="failed")
        snapshot = self.store.add_evidence(page["id"], page["revision"], marked)
        self.assertEqual(self.stored(snapshot, "e1")["origin"], "synthetic")
        self.assertEqual(self.stored(snapshot, "e1")["state"], "failed")

    def test_old_payloads_keep_their_honest_defaults(self) -> None:
        page = working(self.store.snapshot())
        snapshot = self.store.add_evidence(page["id"], page["revision"], self.item("e1"))
        self.assertEqual(self.stored(snapshot, "e1")["origin"], "unspecified")
        self.assertEqual(self.stored(snapshot, "e1")["state"], "complete")

    def test_invalid_supplied_values_are_refused(self) -> None:
        page = working(self.store.snapshot())
        before = self.store.snapshot()
        for bad in (self.item("e1", state="great"), self.item("e2", origin="guessed")):
            with self.assertRaises(ValueError):
                self.store.add_evidence(page["id"], page["revision"], bad)
        self.assertEqual(self.store.snapshot(), before)

    def test_a_complete_result_cannot_rest_on_failed_incremental_evidence(self) -> None:
        page = working(self.store.snapshot())
        failed = self.item("e1", origin="synthetic", state="failed")
        self.store.add_evidence(page["id"], page["revision"], failed)
        page = working(self.store.snapshot())
        before = self.store.snapshot()
        with self.assertRaises(ValueError):
            self.store.submit_result(completion(page, None), at=at(0))
        self.assertEqual(self.store.snapshot(), before)
        errors = [{"error": "Interval 3 failed", "code": "worker_failed", "retryable": False}]
        partial = completion(page, None, "p1", outcome="partial", errors=errors)
        done = self.store.submit_result(partial, at=at(1))
        check_book(done)

    def test_the_legacy_route_cannot_skip_fencing(self) -> None:
        _, successor = decided(self.store)
        item = self.item("e1")
        with self.assertRaises(BookConflict) as bare:
            self.store.add_evidence(successor["id"], successor["revision"], item, at=at(0))
        self.assertEqual(bare.exception.code, "unrelated_page")
        handoff = self.store.claim_delivery("worker-a", at=at(0))
        assert handoff is not None
        claim = claim_of(handoff)
        with self.assertRaises(BookConflict) as silent:
            self.store.add_evidence(successor["id"], successor["revision"], item, claim, at(1))
        self.assertEqual(silent.exception.code, "not_ready")
        self.store.acknowledge_delivery(handoff["continuation_id"], 1, at=at(2))
        wrong = {**claim, "attempt": 2}
        with self.assertRaises(BookConflict) as forged:
            self.store.add_evidence(successor["id"], successor["revision"], item, wrong, at(3))
        self.assertEqual(forged.exception.code, "claim_expired")
        self.store.add_evidence(successor["id"], successor["revision"], item, claim, at(4))
        with self.assertRaises(BookConflict) as expired:
            late = self.item("e2")
            fresh = working(self.store.snapshot())
            self.store.add_evidence(fresh["id"], fresh["revision"], late, claim, at(900))
        self.assertEqual(expired.exception.code, "claim_expired")

    def test_a_replaced_worker_cannot_add_evidence(self) -> None:
        _, successor = decided(self.store)
        slow = self.claim_and_ack("worker-a", 0)
        self.claim_and_ack("worker-b", 100)
        before = self.store.snapshot()
        with self.assertRaises(BookConflict) as late:
            self.store.add_evidence(
                successor["id"], successor["revision"], self.item("e1"), claim_of(slow), at(102)
            )
        self.assertEqual(late.exception.code, "claim_expired")
        self.assertEqual(self.store.snapshot(), before)


class SqliteCase(unittest.TestCase):
    def test_the_database_keeps_one_attempt_record_per_attempt(self) -> None:
        with sqlite3.connect(":memory:") as connection:
            tables.create(connection)
            tries.begin(connection, "c", 1, "w", "2026-10-15T09:00:00+00:00")
            with self.assertRaises(sqlite3.IntegrityError):
                tries.begin(connection, "c", 1, "w2", "2026-10-15T09:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
