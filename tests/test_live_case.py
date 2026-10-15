# Purpose: check a real-data book is truthful, reviewable by a human and continued by a worker.
from pathlib import Path
from typing import Any

from support import NOTE, BookCase, working
from test_science import chips

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.book import BookStore
from hylogger_bridge.pages.live import start
from training import live

QUESTION = "Does the dominant SWIR mineral group change between 0-5 m and 5-10 m in hole FIX001?"


class LiveCaseTests(BookCase):
    def setUp(self) -> None:
        super().setUp()
        self.book = self.path.with_name("live.sqlite3")
        self.hole = chips()
        self.first = start(
            "real-fix001", "Real HyLogger hole FIX001", QUESTION, "A real case.", "Working"
        )
        self.live = BookStore(
            self.book, provider=FixtureProvider(), science=lambda f, n: self.hole, start=self.first
        )

    def prepare(self) -> dict[str, Any]:
        page = working(self.live.snapshot())
        page = working(
            self.live.attach_scene(
                page["id"], page["revision"], Path("pkg"), "FIX001_chips", (5, 10), (0, 5)
            )
        )
        for stage in ("inventory", "qa"):
            page = working(self.live.measure(page["id"], page["revision"], stage))
        return page

    def test_a_live_book_is_truthful_and_the_default_stays_synthetic(self) -> None:
        snapshot = self.live.snapshot()
        page = working(snapshot)
        self.assertEqual((snapshot["source"], snapshot["run_id"]), ("live", "real-fix001"))
        self.assertEqual((page["title"], page["question"]), ("Real HyLogger hole FIX001", QUESTION))
        self.assertNotIn("synthetic", (page["summary"] + page["progress"]).lower())
        default = self.store.snapshot()
        self.assertEqual((default["source"], default["run_id"]), ("synthetic_demo", "demo"))

    def test_a_database_keeps_its_own_case(self) -> None:
        other = start("real-other", "Other", "Q?", "S", "P")
        with self.assertRaises(ValueError):
            BookStore(self.book, start=other)
        again = BookStore(self.book)
        self.assertEqual(again.snapshot()["run_id"], "real-fix001")

    def test_the_first_page_finishes_for_review_then_a_worker_continues_after_the_human(
        self,
    ) -> None:
        self.prepare()
        shown = live.finish_first(self.live, "")
        self.assertEqual(
            (shown["status"], shown["outcome"], shown["source"]), ("ready", "complete", "live")
        )
        self.assertIn("limits", shown["evidence_ids"])
        page = working(self.live.snapshot())
        with self.assertRaises(SystemExit):
            live.continue_case(self.live)
        snapshot = self.live.decide(page["id"], page["revision"], "accept", NOTE, "decision-1")
        locked = next(p for p in snapshot["pages"] if p["id"] == page["id"])
        successor = working(snapshot)
        self.assertEqual(locked["decision"]["note"], NOTE)
        self.assertEqual(locked["decision"]["actor"], {"kind": "human"})
        self.assertEqual(successor["question"], QUESTION)
        self.assertNotIn("synthetic", (successor["summary"] + successor["progress"]).lower())
        done = live.continue_case(self.live)
        self.assertEqual(done["status"], "ready")
        final = self.live.snapshot()
        self.assertEqual(next(p for p in final["pages"] if p["id"] == page["id"]), locked)
        grown = next(p for p in final["pages"] if p["id"] == successor["id"])
        self.assertEqual([e["id"] for e in grown["evidence"]][:3], ["inventory", "qa", "compare"])
        self.assertEqual(final["continuations"][0]["state"], "completed")
        self.assertEqual(grown["action"]["type"], "interval_compare")

    def test_accept_runs_the_comparison(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        self.live.decide(
            page["id"], page["revision"], "accept", "Looks good, proceed", "dec-accept"
        )
        done = live.continue_case(self.live)
        self.assertEqual(done["status"], "ready")
        self.assertIn("compare", done)
        snap = self.live.snapshot()
        current = working(snap)
        self.assertEqual(current["action"]["type"], "interval_compare")
        self.assertEqual(current["outcome"], "complete")
        evidence_ids = [e["id"] for e in current["evidence"]]
        self.assertEqual(evidence_ids[:3], ["inventory", "qa", "compare"])
        self.assertIn("limits", evidence_ids)
        self.assertEqual(snap["continuations"][0]["state"], "completed")

    def test_reject_runs_no_calculation(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        self.live.decide(
            page["id"], page["revision"], "reject", "Stop; do not compare.", "decision-reject"
        )
        done = live.continue_case(self.live)
        self.assertEqual(done["status"], "ready")
        self.assertTrue(done.get("stopped"))
        snap = self.live.snapshot()
        current = working(snap)
        self.assertEqual(current["action"]["type"], "stop")
        self.assertEqual(current["outcome"], "complete")
        evidence_ids = [e["id"] for e in current["evidence"]]
        self.assertIn("expert_stop", evidence_ids)
        self.assertIn("limits", evidence_ids)
        self.assertNotIn("inventory", evidence_ids)
        self.assertNotIn("qa", evidence_ids)
        self.assertNotIn("compare", evidence_ids)
        import sqlite3

        with sqlite3.connect(self.book) as conn:
            row = conn.execute(
                "SELECT scene FROM scenes WHERE page_id=?", (current["id"],)
            ).fetchone()
            self.assertIsNone(row)
        self.assertEqual(snap["continuations"][0]["state"], "completed")

    def test_modify_with_valid_bounds_compares_exactly_those_bounds(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        self.live.decide(
            page["id"],
            page["revision"],
            "modify",
            "Compare 6–8 m against 2–4 m instead.",
            "decision-mod-valid",
        )
        done = live.continue_case(self.live, target=(6.0, 8.0), reference=(2.0, 4.0))
        self.assertEqual(done["status"], "ready")
        self.assertIn("compare", done)
        snap = self.live.snapshot()
        current = working(snap)
        self.assertEqual(current["action"]["type"], "interval_compare")
        self.assertEqual(current["outcome"], "complete")
        evidence_ids = [e["id"] for e in current["evidence"]]
        self.assertIn("operator_bounds", evidence_ids)
        self.assertIn("compare", evidence_ids)
        import json
        import sqlite3

        with sqlite3.connect(self.book) as conn:
            row = conn.execute(
                "SELECT scene FROM scenes WHERE page_id=?", (current["id"],)
            ).fetchone()
            self.assertIsNotNone(row)
            scene = json.loads(row[0])
            self.assertEqual(scene["target"], [6.0, 8.0])
            self.assertEqual(scene["reference"], [2.0, 4.0])
        self.assertEqual(snap["continuations"][0]["state"], "completed")

    def test_modify_with_invalid_bounds_is_refused(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        self.live.decide(
            page["id"],
            page["revision"],
            "modify",
            "Compare 10–15 m against 5–10 m instead.",
            "decision-mod-inv",
        )
        before = self.live.snapshot()
        # 1. Bounds exceeding hole range (depth range of chips is [0.0, 10.0])
        with self.assertRaises(ValueError) as ctx:
            live.continue_case(self.live, target=(10.0, 15.0), reference=(5.0, 10.0))
        self.assertIn("outside hole depth range", str(ctx.exception))
        self.assertEqual(self.live.snapshot(), before)

        # 2. Inverted bounds
        with self.assertRaises(ValueError) as ctx:
            live.continue_case(self.live, target=(8.0, 6.0), reference=(2.0, 4.0))
        self.assertIn("bounds must be finite and increasing", str(ctx.exception))
        self.assertEqual(self.live.snapshot(), before)

        # 3. Supplying target without reference
        with self.assertRaises(ValueError) as ctx:
            live.continue_case(self.live, target=(6.0, 8.0), reference=None)
        self.assertIn("Both --target and --reference", str(ctx.exception))
        self.assertEqual(self.live.snapshot(), before)

        # 4. Negative bounds
        with self.assertRaises(ValueError) as ctx:
            live.continue_case(self.live, target=(-2.0, 4.0), reference=(0.0, 2.0))
        self.assertIn("must be non-negative", str(ctx.exception))
        self.assertEqual(self.live.snapshot(), before)

    def test_modify_without_bounds_requests_clarification(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        self.live.decide(
            page["id"],
            page["revision"],
            "modify",
            "Compare different depths.",
            "decision-mod-nobounds",
        )
        done = live.continue_case(self.live)
        self.assertEqual(done["status"], "ready")
        self.assertTrue(done.get("clarification_needed"))
        snap = self.live.snapshot()
        current = working(snap)
        self.assertEqual(current["action"]["type"], "clarify")
        self.assertEqual(current["outcome"], "complete")
        evidence_ids = [e["id"] for e in current["evidence"]]
        self.assertIn("clarify_needed", evidence_ids)
        self.assertIn("limits", evidence_ids)
        self.assertNotIn("inventory", evidence_ids)
        self.assertNotIn("compare", evidence_ids)
        self.assertEqual(snap["continuations"][0]["state"], "completed")

    def test_recovery_after_clarification_works(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page1 = working(self.live.snapshot())
        self.live.decide(
            page1["id"], page1["revision"], "modify", "Need adjustment.", "decision-recov-1"
        )
        done1 = live.continue_case(self.live)
        self.assertEqual(done1["status"], "ready")
        page2 = working(self.live.snapshot())
        self.assertEqual(page2["action"]["type"], "clarify")
        self.assertEqual(page2["status"], "ready")

        # Expert reviews ready Page 2 and records a new decision on it
        self.live.decide(
            page2["id"], page2["revision"], "modify", "Use 6-8 m and 2-4 m.", "decision-recov-2"
        )
        done2 = live.continue_case(self.live, target=(6.0, 8.0), reference=(2.0, 4.0))
        self.assertEqual(done2["status"], "ready")
        self.assertIn("compare", done2)
        page3 = working(self.live.snapshot())
        self.assertEqual(page3["action"]["type"], "interval_compare")
        self.assertEqual(page3["outcome"], "complete")
        evidence_ids = [e["id"] for e in page3["evidence"]]
        self.assertIn("operator_bounds", evidence_ids)
        self.assertIn("compare", evidence_ids)
        conts = self.live.snapshot()["continuations"]
        self.assertEqual(len(conts), 2)
        self.assertTrue(all(c["state"] == "completed" for c in conts))

    def test_a_second_continue_with_nothing_pending_has_no_effect(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        self.live.decide(page["id"], page["revision"], "accept", NOTE, "decision-done")
        live.continue_case(self.live)
        before = self.live.snapshot()
        with self.assertRaises(SystemExit) as ctx:
            live.continue_case(self.live)
        self.assertIn("No human decision is waiting", str(ctx.exception))
        self.assertEqual(self.live.snapshot(), before)

    def test_a_replayed_result_with_the_same_request_id_has_no_effect(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        self.live.decide(page["id"], page["revision"], "accept", NOTE, "decision-replay")
        live.continue_case(self.live)
        snap_after = self.live.snapshot()
        import json
        import sqlite3

        with sqlite3.connect(self.book) as conn:
            row = conn.execute("SELECT payload FROM results ORDER BY rowid DESC LIMIT 1").fetchone()
            self.assertIsNotNone(row)
            payload = json.loads(row[0])
        res = self.live.submit_result(payload)
        self.assertEqual(res, snap_after)

    def test_exact_note_and_locked_page_unchanged_after_reopening_bookstore(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        exact_note = "Detailed expert review note with special chars: 10–15 m & 5–10 m. Ref: #123."
        snapshot = self.live.decide(
            page["id"], page["revision"], "accept", exact_note, "decision-exact"
        )
        locked_before = next(p for p in snapshot["pages"] if p["id"] == page["id"])
        live.continue_case(self.live)
        reopened = BookStore(self.book)
        reopened_snap = reopened.snapshot()
        locked_after = next(p for p in reopened_snap["pages"] if p["id"] == page["id"])
        self.assertEqual(locked_after["decision"]["note"], exact_note)
        self.assertEqual(locked_after["decision"]["actor"], {"kind": "human"})
        self.assertEqual(locked_after["revision"], locked_before["revision"])
        self.assertEqual(locked_after["status"], "locked")

    def test_unknown_choice_is_refused_with_no_state_change(self) -> None:
        self.prepare()
        live.finish_first(self.live, "")
        page = working(self.live.snapshot())
        self.live.decide(page["id"], page["revision"], "accept", NOTE, "decision-bogus")
        import json
        import sqlite3

        with sqlite3.connect(self.book) as conn:
            row = conn.execute("SELECT data FROM book WHERE id=1").fetchone()
            book_data = json.loads(row[0])
            for p in book_data["pages"]:
                if p["id"] == page["id"] and "decision" in p:
                    p["decision"]["choice"] = "unsupported_action"
            conn.execute("UPDATE book SET data=? WHERE id=1", (json.dumps(book_data),))
            conn.commit()
        before = self.live.snapshot()
        with self.assertRaises(ValueError) as ctx:
            live.continue_case(self.live)
        self.assertIn("Refusing unrecognised human choice", str(ctx.exception))
        after = self.live.snapshot()
        self.assertEqual(before, after)


if __name__ == "__main__":
    import unittest

    unittest.main()
