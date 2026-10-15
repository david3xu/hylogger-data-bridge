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
        snapshot = self.live.decide(page["id"], page["revision"], "modify", NOTE, "decision-1")
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


if __name__ == "__main__":
    import unittest

    unittest.main()
