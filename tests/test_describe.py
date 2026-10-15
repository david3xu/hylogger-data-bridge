# Purpose: verify human-readable scientific evidence descriptions and measure() integration.
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_science import chips, hole

from hylogger_bridge.book import BookStore
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.pages.live import start
from hylogger_bridge.science import features, request
from hylogger_bridge.science.describe import describe
from hylogger_bridge.store import measures


class DescribeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hole = chips()
        self.target = (5.0, 10.0)
        self.reference = (0.0, 5.0)
        self.known = request.measured(self.hole, self.target, self.reference)

    def test_metres_labelled_reference_target(self) -> None:
        for stage in ("inventory", "qa", "compare"):
            label, value = describe(
                self.hole, self.target, self.reference, stage, self.known[stage]
            )
            self.assertTrue(label.startswith("Scientific"))
            self.assertIn("Reference 0–5 m", value)
            self.assertIn("Target 5–10 m", value)

    def test_nn_counts(self) -> None:
        # QA stage
        label, value = describe(self.hole, self.target, self.reference, "qa", self.known["qa"])
        # Reference has 15 spots, 14 clean (valid), 5 expected grid positions (all 5 covered),
        # 13 clean spots with SWIR group
        self.assertIn("valid spots 14/15 (93.3%)", value)
        self.assertIn("covered grid positions 5/5 (100.0%)", value)
        self.assertIn("valid spots with a SWIR group 13/14 (92.9%)", value)

        # Target has 15 spots, 15 clean, 5 expected positions, 15 with SWIR group
        self.assertIn("valid spots 15/15 (100.0%)", value)
        self.assertIn("covered grid positions 5/5 (100.0%)", value)
        self.assertIn("valid spots with a SWIR group 15/15 (100.0%)", value)

        # Inventory stage
        label_inv, value_inv = describe(
            self.hole, self.target, self.reference, "inventory", self.known["inventory"]
        )
        self.assertIn("Reference 0–5 m: 15 spots (5 expected grid positions)", value_inv)
        self.assertIn("Target 5–10 m: 15 spots (5 expected grid positions)", value_inv)

    def test_group_names_with_shares(self) -> None:
        label, value = describe(
            self.hole, self.target, self.reference, "compare", self.known["compare"]
        )
        # In reference: 13 valid spots with SWIR group, all KAOLIN
        self.assertIn("KAOLIN 13/13 (100.0%)", value)
        # In target: 15 valid spots with SWIR group, all SMECTITE
        self.assertIn("SMECTITE 15/15 (100.0%)", value)

    def test_metric_definitions(self) -> None:
        # QA definitions
        _, qa_val = describe(self.hole, self.target, self.reference, "qa", self.known["qa"])
        self.assertIn("clean spots only (TSG Final Mask)", qa_val)
        self.assertIn("INVALID, ASPECTRAL, NOTAROK", qa_val)

        # Compare definitions
        _, cmp_val = describe(
            self.hole, self.target, self.reference, "compare", self.known["compare"]
        )
        self.assertIn("TSG Grp1 sTSAS interpretations, not new mineral identification", cmp_val)
        self.assertIn("total variation distance: 0 identical, 1 completely different", cmp_val)
        self.assertIn("group_shift = 1", cmp_val)
        self.assertIn(
            "lead_changed = 1 (changed; target leaders: 1, reference leaders: 1)", cmp_val
        )

    def test_empty_and_tie_cases(self) -> None:
        # 1. Empty interval case
        empty_target = (20.0, 25.0)  # outside hole depth
        empty_known = request.measured(self.hole, empty_target, self.reference)
        _, empty_cmp = describe(
            self.hole, empty_target, self.reference, "compare", empty_known["compare"]
        )
        self.assertIn("Target 20–25 m: none", empty_cmp)
        self.assertIn("group_shift = None", empty_cmp)
        self.assertIn("lead_changed = None (no answers", empty_cmp)

        _, empty_qa = describe(self.hole, empty_target, self.reference, "qa", empty_known["qa"])
        self.assertIn("valid spots 0/0 (0.0%)", empty_qa)
        self.assertIn("covered grid positions 0/5 (0.0%)", empty_qa)

        # Irregular grid hole -> coverage unknown
        irr_hole = hole([(1.0, True, "A"), (1.3, True, "B"), (2.7, True, "C")], name="IRR001")
        irr_known = request.measured(irr_hole, (0.0, 2.0), (2.0, 4.0))
        _, irr_qa = describe(irr_hole, (0.0, 2.0), (2.0, 4.0), "qa", irr_known["qa"])
        self.assertIn("coverage unknown", irr_qa)
        _, irr_inv = describe(irr_hole, (0.0, 2.0), (2.0, 4.0), "inventory", irr_known["inventory"])
        self.assertIn("irregular grid", irr_inv)

        # 2. Tie case: construct hole with tied mineral groups
        tied_hole = hole(
            [
                (1.5, True, "KAOLIN"),
                (1.5, True, "SMECTITE"),
                (6.5, True, "ILLITE"),
            ],
            name="TIE001",
        )
        tied_target = (5.0, 10.0)
        tied_ref = (0.0, 5.0)
        tied_known = request.measured(tied_hole, tied_target, tied_ref)
        _, tied_cmp = describe(tied_hole, tied_target, tied_ref, "compare", tied_known["compare"])
        self.assertIn(
            "lead_changed = None (tie; target leaders: 1, reference leaders: 2)", tied_cmp
        )
        self.assertIn("KAOLIN 1/2 (50.0%)", tied_cmp)
        self.assertIn("SMECTITE 1/2 (50.0%)", tied_cmp)

    def test_values_unchanged(self) -> None:
        for stage in ("inventory", "qa", "compare"):
            orig = copy.deepcopy(self.known[stage])
            describe(self.hole, self.target, self.reference, stage, self.known[stage])
            self.assertEqual(self.known[stage], orig)

    def test_measure_stores_identical_measurement_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_book.sqlite3"
            start_page = start("real-chips", "Real Hole", "Question?", "Summary.", "Progress")
            store = BookStore(
                db_path,
                science=lambda folder, pkg: self.hole,
                start=start_page,
            )
            page = store.snapshot()["pages"][0]
            store.attach_scene(
                page["id"],
                page["revision"],
                Path("dummy_folder"),
                "chips_pkg",
                self.target,
                self.reference,
            )
            snap = store.snapshot()
            page = snap["pages"][0]

            for stage in ("inventory", "qa", "compare"):
                snap = store.measure(page["id"], page["revision"], stage)
                page = snap["pages"][0]
                ev = next(e for e in page["evidence"] if e["id"] == stage)
                validate("Evidence", ev)
                self.assertEqual(ev["origin"], "actual")
                self.assertEqual(ev["state"], "complete")
                self.assertEqual(ev["kind"], request.KINDS[stage])
                self.assertEqual(ev["source"], f"{self.hole.hole_id} via pytsg; {features.METHOD}")

                # Check measurements table
                with sqlite3.connect(db_path) as conn:
                    row = conn.execute(
                        "SELECT features FROM measurements WHERE page_id=? AND evidence_id=?",
                        (page["id"], stage),
                    ).fetchone()
                    self.assertIsNotNone(row)
                    stored_features = json.loads(row[0])
                    # Stored measurement features must be byte/value-identical to request.measured
                    expected_features = self.known[stage]
                    self.assertEqual(stored_features, expected_features)
                    # And trusted features retrieval verifies hash match
                    trusted_features = measures.trusted(conn, page)
                    self.assertIn(stage, trusted_features)
                    self.assertEqual(trusted_features[stage], expected_features)


if __name__ == "__main__":
    unittest.main()
