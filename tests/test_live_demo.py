# Purpose: check the one-step real-case command and its labelled route without model weights.
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any
from unittest import mock

from support import NOTE, working
from test_science import chips

from hylogger_bridge.book import BookStore
from training import live


class DemoTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.book = Path(scratch.name) / "real-fix001.sqlite3"
        self.hole = chips()
        quiet = mock.patch("builtins.print")
        quiet.start()
        self.addCleanup(quiet.stop)

    def science(self, folder: str, name: str) -> Any:
        return self.hole

    def args(self, **changes: Any) -> Namespace:
        base: dict[str, Any] = {
            "book": self.book,
            "package": Path("pkg"),
            "package_id": "FIX001_chips",
            "target": [5.0, 10.0],
            "reference": [0.0, 5.0],
            "instruction": "",
            "model": None,
            "model_python": None,
        }
        return Namespace(**{**base, **changes})

    def test_case_files_sit_beside_the_book(self) -> None:
        files = live.case_files(Path("outputs/live-book/real-x.sqlite3"))
        self.assertEqual(files["request"], Path("outputs/live-book/real-x.request.json"))
        self.assertEqual(files["advice"], Path("outputs/live-book/real-x.advice.json"))
        self.assertEqual(files["first-page"], Path("outputs/live-book/real-x.first-page.json"))

    def test_without_a_model_the_first_page_is_ready_with_labelled_fixture_advice(self) -> None:
        summary = live.demo(self.args(), science=self.science)
        self.assertEqual((summary["status"], summary["source"]), ("ready", "live"))
        self.assertEqual(summary["assessment_origin"], "fixture")
        self.assertIn("qa", summary["evidence_ids"])
        saved = json.loads(live.case_files(self.book)["first-page"].read_text())
        self.assertEqual(saved, summary)
        page = working(BookStore(self.book).snapshot())
        limits = next(e for e in page["evidence"] if e["id"] == "limits")
        self.assertIn("labelled fixture", limits["value"])
        self.assertNotIn("experimental local model", limits["value"])
        self.assertEqual(page["assessment"]["origin"], "fixture")

    def test_the_fixture_case_is_reviewed_by_a_human_then_continued(self) -> None:
        live.demo(self.args(), science=self.science)
        store = BookStore(self.book, science=self.science)
        page = working(store.snapshot())
        store.decide(page["id"], page["revision"], "accept", NOTE, "decision-1")
        done = live.continue_case(store)
        self.assertEqual(done["status"], "ready")
        locked = next(p for p in store.snapshot()["pages"] if p["id"] == page["id"])
        self.assertEqual(locked["decision"]["note"], NOTE)

    def test_an_existing_book_is_never_reused(self) -> None:
        self.book.write_bytes(b"keep")
        with self.assertRaises(SystemExit):
            live.demo(self.args(), science=self.science)
        self.assertEqual(self.book.read_bytes(), b"keep")

    def test_a_model_needs_its_environment_before_anything_is_written(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HYLOGGER_MODEL_PYTHON", None)
            with self.assertRaises(SystemExit):
                live.demo(self.args(model=Path("bundle")), science=self.science)
        self.assertFalse(self.book.exists())

    def test_record_takes_exactly_one_advice_source(self) -> None:
        parser = live.parser()
        base = ["record", "--book", "b.sqlite3", "--out", "o.json"]
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                parser.parse_args(base)
            with self.assertRaises(SystemExit):
                parser.parse_args([*base, "--fixture", "--advice", "a.json"])
        chosen = parser.parse_args([*base, "--fixture"])
        self.assertTrue(chosen.fixture)
        self.assertIsNone(chosen.advice)

    def test_demo_defaults_name_the_documented_case(self) -> None:
        chosen = live.parser().parse_args(["demo", "--book", "b.sqlite3"])
        self.assertEqual(chosen.package, Path("data/raw/nvcl/SWMB007s_chips/pkg"))
        self.assertEqual(
            (chosen.package_id, chosen.target, chosen.reference),
            ("SWMB007s_chips", [5.0, 10.0], [0.0, 5.0]),
        )
        self.assertIsNone(chosen.model)
