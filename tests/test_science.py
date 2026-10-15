# Purpose: check the scientific adapter, calculations and live feature path on tiny labelled fixtures.
import math
import unittest
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from support import NOTE, BookCase, page_of, ready, working

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.book import BookStore
from hylogger_bridge.conflict import BookConflict
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.science import features, package, request
from hylogger_bridge.science.hole import Hole
from training import rubric


def hole(rows: Sequence[tuple[float, bool, str | None]], name: str = "FIX001") -> Hole:
    return Hole(
        hole_id=name,
        depth=tuple(r[0] for r in rows),
        valid=tuple(r[1] for r in rows),
        swir=tuple(r[2] for r in rows),
        tir=tuple(r[2] for r in rows),
        files=(("FIX_tsg.tsg", "0" * 64),),
    )


def chips() -> Hole:
    """Ten metres, three spots per position at x.5. Hand-checkable by position:

    metres 0-4 are KAOLIN, except one unanswered spot at 1.5 and one masked spot at 3.5;
    metres 5-9 are SMECTITE.
    """
    rows = []
    for position in range(10):
        for spot in range(3):
            group: str | None = "KAOLIN" if position < 5 else "SMECTITE"
            valid = not (position == 3 and spot == 2)
            if position == 1 and spot == 0:
                group = None
            rows.append((position + 0.5, valid, group))
    return hole(rows)


class CalculationTests(unittest.TestCase):
    def test_a_covered_interval_by_hand(self) -> None:
        a = features.qa(chips(), 5, 10)
        self.assertEqual(
            a,
            {
                "spots": 15,
                "valid_fraction": 1.0,
                "expected_positions": 5,
                "coverage": 1.0,
                "swir_fraction": 1.0,
                "tir_fraction": 1.0,
            },
        )

    def test_masks_and_missing_answers_reduce_fractions_but_not_coverage(self) -> None:
        b = features.qa(chips(), 0, 5)
        self.assertEqual((b["spots"], b["valid_fraction"]), (15, round(14 / 15, 4)))
        self.assertEqual(b["swir_fraction"], round(13 / 14, 4))
        self.assertEqual(b["coverage"], 1.0)

    def test_good_rows_in_two_positions_are_not_coverage_of_ten_metres(self) -> None:
        rows = [(p + 0.5, True, "A") for p in range(10) for _ in range(3)]
        rows += [(10.5, True, "A")] * 3 + [(11.5, True, "A")] * 3
        gapped = hole(rows)
        got = features.qa(gapped, 10, 20)
        self.assertEqual((got["valid_fraction"], got["swir_fraction"]), (1.0, 1.0))
        self.assertEqual((got["expected_positions"], got["coverage"]), (10, 0.2))

    def test_an_empty_but_valid_interval_has_zero_coverage_and_no_invented_fractions(self) -> None:
        got = features.qa(chips(), 20, 25)
        self.assertEqual((got["spots"], got["valid_fraction"], got["coverage"]), (0, None, 0.0))
        self.assertIsNone(got["swir_fraction"])

    def test_bounds_are_half_open_and_must_be_finite_and_increasing(self) -> None:
        h = chips()
        self.assertEqual(features.spots(h, 5.5, 6.5), [15, 16, 17])
        self.assertEqual(features.spots(h, 5.0, 5.5), [])
        for top, bottom in ((5, 5), (6, 5), (math.nan, 5), (0, math.inf), (-math.inf, 3)):
            with self.subTest(top=top, bottom=bottom), self.assertRaises(ValueError):
                features.qa(h, top, bottom)
        with self.assertRaises(ValueError):
            hole([(math.nan, True, "A")])

    def test_repeated_spot_depths_stay_separate_spots(self) -> None:
        got = features.qa(hole([(0.5, True, "A")] * 3 + [(1.5, True, "A")]), 0, 1)
        self.assertEqual((got["spots"], got["expected_positions"], got["coverage"]), (3, 1, 1.0))

    def test_comparison_by_hand(self) -> None:
        got = features.compare(chips(), (5, 10), (0, 5))
        self.assertEqual(
            got,
            {"group_shift": 1.0, "lead_changed": 1, "target_leaders": 1, "reference_leaders": 1},
        )
        same = features.compare(chips(), (0, 3), (3, 5))
        self.assertEqual((same["group_shift"], same["lead_changed"]), (0.0, 0))

    def test_a_tied_lead_is_not_a_definite_change(self) -> None:
        tied = hole([(0.5, True, "A")] * 3 + [(0.5, True, "B")] * 3 + [(1.5, True, "B")] * 6)
        got = features.compare(tied, (0, 1), (1, 2))
        self.assertEqual(got["group_shift"], 0.5)
        self.assertIsNone(got["lead_changed"])
        self.assertEqual((got["target_leaders"], got["reference_leaders"]), (2, 1))

    def test_an_interval_without_answers_gives_no_comparison(self) -> None:
        none = hole([(0.5, True, None)] * 3 + [(1.5, True, "B")] * 3)
        got = features.compare(none, (0, 1), (1, 2))
        self.assertEqual((got["group_shift"], got["lead_changed"]), (None, None))
        self.assertEqual((got["target_leaders"], got["reference_leaders"]), (None, 1))


class Table:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def __getitem__(self, column: str) -> "Table":
        return self

    def tolist(self) -> list[Any]:
        return self.values


class DecodeTests(unittest.TestCase):
    def block(self, values: list[Any]) -> Any:
        names = {0: "SILICA", 1: "KAOLIN", 2: "WHITE-MICA", 3: "SMECTITE"}
        return SimpleNamespace(
            scalars=Table(values),
            bandheaders=[SimpleNamespace(name="Grp1 sTSAS", class_number=5)],
            classes={5: SimpleNamespace(classes=names)},
        )

    def test_class_indices_decode_through_the_class_table(self) -> None:
        got = package._groups(self.block([3.0, 1.0, -3.4028233e38, 9.0, 0.0]), "Grp1 sTSAS")
        self.assertEqual(got, ("SMECTITE", "KAOLIN", None, None, "SILICA"))

    def test_strings_and_non_answers(self) -> None:
        got = package._groups(
            self.block(["KAOLIN", "", "INVALID", "NOTAROK", " SILICA "]), "Grp1 sTSAS"
        )
        self.assertEqual(got, ("KAOLIN", None, None, None, "SILICA"))


class IdentityTests(unittest.TestCase):
    def test_the_declared_name_settles_identity_when_nothing_disagrees(self) -> None:
        found, seen = package.identify("EGD002_chips", {"file names": {"EGD002_chips"}})
        self.assertEqual(found, "EGD002")
        self.assertIn(("file names", "EGD002_chips"), seen)
        self.assertEqual(package.identify("SWMB005d_chips", {})[0], "SWMB005d")

    def test_case_and_chips_suffix_are_not_conflicts(self) -> None:
        claims = {"header": {"SWMB005d_Chips"}, "class": {"swmb005d_chips"}}
        self.assertEqual(package.identify("SWMB005d_chips", claims)[0], "SWMB005d")

    def test_a_conflicting_or_ambiguous_identity_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            package.identify("EGD001_chips", {"class": {"EGD002"}})
        with self.assertRaises(ValueError):
            package.identify("EGD001_chips", {"header": {"EGD001", "EGD002"}})
        with self.assertRaises(ValueError):
            package.identify("", {})


class LiveTests(BookCase):
    """One shared feature path: the book's own request carries the same numbers as training."""

    def setUp(self) -> None:
        super().setUp()
        self.hole = chips()
        self.seen: list[dict[str, Any]] = []
        outer = self

        class Spy:
            def assess(self, ask: dict[str, Any], at: str) -> dict[str, Any]:
                outer.seen.append(ask)
                if outer.during is not None:
                    outer.during()
                return FixtureProvider().assess(ask, at)

        self.during: Any = None
        self.spy = Spy()
        self.store = BookStore(self.path, provider=self.spy, science=lambda folder, name: self.hole)

    def scene(self) -> dict[str, Any]:
        page = working(self.store.snapshot())
        self.store.attach_scene(
            page["id"], page["revision"], Path("pkg"), "FIX001_chips", (5, 10), (0, 5)
        )
        return page

    def measure(self, stage: str) -> dict[str, Any]:
        page = working(self.store.snapshot())
        return working(self.store.measure(page["id"], page["revision"], stage))

    def ask(self) -> dict[str, Any]:
        page = working(self.store.snapshot())
        return working(self.store.request_assessment(page["id"], page["revision"], instruction="x"))

    def test_the_book_prepares_exactly_the_features_training_uses(self) -> None:
        self.scene()
        self.measure("inventory")
        page = self.measure("qa")
        self.ask()
        (got,) = self.seen
        validate("AssessmentRequest", got)
        self.assertEqual(got["page_id"], page["id"])
        self.assertEqual(got["state_revision"], page["revision"])
        self.assertEqual(got["evidence"], request.evidence(self.hole, (5, 10), (0, 5), "qa"))
        self.assertEqual(got["candidates"], request.candidates((5, 10), (0, 5)))

    def test_reload_agrees(self) -> None:
        self.scene()
        self.measure("inventory")
        self.ask()
        again = BookStore(self.path, provider=self.spy, science=lambda folder, name: self.hole)
        page = working(again.snapshot())
        again.request_assessment(page["id"], page["revision"], instruction="x")
        self.assertEqual(self.seen[0]["evidence"], self.seen[1]["evidence"])
        self.assertEqual(self.seen[0]["evidence"][0]["features"]["target_positions"], 5)

    def test_only_persisted_evidence_gets_features_and_generic_pages_stay_generic(self) -> None:
        self.scene()
        self.ask()
        self.assertEqual(self.seen[0]["evidence"], [])
        plain = BookStore(Path(str(self.path) + ".plain"), provider=self.spy)
        page = ready(plain)
        plain.request_assessment(page["id"], page["revision"], instruction="x")
        self.assertTrue(all(e["features"] == {} for e in self.seen[1]["evidence"]))
        self.assertEqual(len(self.seen[1]["candidates"]), 5)

    def test_advice_goes_stale_when_evidence_is_persisted_during_inference(self) -> None:
        self.scene()
        self.measure("inventory")
        self.during = lambda: self.measure("qa")
        with self.assertRaises(BookConflict) as caught:
            self.ask()
        self.assertEqual(caught.exception.code, "stale_revision")

    def test_a_page_locked_during_inference_refuses_the_advice(self) -> None:
        page = self.scene()
        self.measure("inventory")

        def lock() -> None:
            ready(self.store)
            current = working(self.store.snapshot())
            self.store.decide(current["id"], current["revision"], "modify", NOTE, "decision-1")

        self.during = lock
        with self.assertRaises(BookConflict):
            self.ask()
        locked = page_of(self.store.snapshot(), page["id"])
        self.assertIsNone(locked["assessment"])
        with self.assertRaises(BookConflict) as caught:
            self.store.attach_scene(
                locked["id"], locked["revision"], Path("pkg"), "FIX001_chips", (5, 10), (0, 5)
            )
        self.assertEqual(caught.exception.code, "page_locked")

    def test_a_changed_package_or_bad_intervals_are_refused(self) -> None:
        page = working(self.store.snapshot())
        with self.assertRaises(ValueError):
            self.store.attach_scene(
                page["id"], page["revision"], Path("pkg"), "FIX001_chips", (5, 5), (0, 5)
            )
        self.scene()
        self.measure("inventory")
        self.hole = replace(self.hole, files=(("FIX_tsg.tsg", "1" * 64),))
        with self.assertRaises(ValueError):
            self.ask()

    def test_measuring_a_page_without_a_scene_is_refused(self) -> None:
        page = working(self.store.snapshot())
        with self.assertRaises(ValueError):
            self.store.measure(page["id"], page["revision"], "qa")


class RubricTests(unittest.TestCase):
    def facts(self, **changes: Any) -> dict[str, Any]:
        base = {
            "target_positions": 5,
            "reference_positions": 5,
            "target_coverage": 1.0,
            "reference_coverage": 1.0,
            "target_valid": 1.0,
            "reference_valid": 1.0,
            "target_swir": 1.0,
            "reference_swir": 1.0,
        }
        return {**base, **changes}

    def test_numbers_decide_between_comparing_and_asking(self) -> None:
        good, gapped = self.facts(), self.facts(target_coverage=0.2)
        self.assertEqual(rubric.choose("difference", "none", "qa", good), "interval_compare")
        self.assertEqual(rubric.choose("difference", "none", "qa", gapped), "clarify")
        self.assertEqual(rubric.choose("summary", "none", "compare", good), "stop")
        self.assertEqual(rubric.choose("summary", "none", "compare", gapped), "clarify")

    def test_the_question_and_instruction_decide_on_the_same_evidence(self) -> None:
        good = self.facts()
        self.assertEqual(rubric.choose("coverage", "none", "qa", good), "stop")
        self.assertEqual(rubric.choose("difference", "none", "qa", good), "interval_compare")
        self.assertEqual(
            rubric.choose("difference", "direct", "inventory", good), "interval_compare"
        )
        self.assertEqual(rubric.choose("difference", "check_first", "inventory", good), "qa_check")
        self.assertEqual(rubric.choose("coverage", "direct", "inventory", good), "qa_check")

    def test_an_interval_of_one_sampling_position_cannot_be_compared(self) -> None:
        self.assertEqual(
            rubric.choose("difference", "none", "inventory", self.facts(target_positions=1)),
            "clarify",
        )
        self.assertEqual(
            rubric.choose("difference", "none", "inventory", self.facts(reference_positions=None)),
            "clarify",
        )


class RecordTests(unittest.TestCase):
    def test_units_pair_different_questions_on_identical_evidence_and_load(self) -> None:
        import json
        import random
        import tempfile

        from training import real
        from training.records import load

        source = {
            "source_url": "https://example.invalid/FIX001.zip",
            "source_sha256": "a" * 64,
        }
        rows = []
        for split in ("train", "validation", "test"):
            rng = random.Random(split)
            window = ((5.0, 10.0), (0.0, 5.0))
            first, second = real.unit(chips(), f"FAM-{split}", split, source, window, 5, "qa", rng)
            self.assertEqual(first["request"]["evidence"], second["request"]["evidence"])
            self.assertNotEqual(
                (first["meta"]["kind"], first["meta"]["stance"]),
                (second["meta"]["kind"], second["meta"]["stance"]),
            )
            for row in (first, second):
                row["id"] = f"{split}-{row['id']}"
                row["provenance"]["tool_version"] = "fixture"
            rows += [first, second]
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "records.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            loaded = load(path)
        self.assertEqual({row["label_origin"] for row in loaded}, {"teaching_rule"})
        self.assertEqual({row["origin"] for row in loaded}, {"organiser"})


if __name__ == "__main__":
    unittest.main()
