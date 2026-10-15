# Purpose: check that the comparison refuses mismatched baselines and incomplete predictions.
import unittest
from typing import Any

from training import evaluate


def row(
    name: str,
    gold: str,
    question: str = "Q",
    evidence: int = 0,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ids = ["cand-qa_check", "cand-interval_compare", "cand-clarify", "cand-stop"]
    return {
        "id": name,
        "gold": gold,
        "meta": {"kind": "difference", "stance": "none", "stage": "qa"},
        "request": {
            "question": question,
            "instruction": "",
            "evidence": [{"evidence_id": "qa", "features": {"x": evidence}}],
            "candidates": [
                {"id": i, "action_type": i[5:], "arguments": arguments or {}} for i in ids
            ],
        },
    }


def prediction(r: dict[str, Any], pred: str) -> dict[str, Any]:
    scores = {c["id"]: 0.25 for c in r["request"]["candidates"]}
    return {"id": r["id"], "gold": r["gold"], "pred": pred, "scores": scores}


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [row("a", "cand-clarify"), row("b", "cand-stop")]
        self.good = {"predictions": [prediction(r, "cand-clarify") for r in self.rows]}

    def test_one_valid_prediction_per_row_is_accepted(self) -> None:
        self.assertEqual(
            evaluate.check(self.good, self.rows, "m"), {"a": "cand-clarify", "b": "cand-clarify"}
        )

    def test_missing_extra_duplicate_and_altered_predictions_are_refused(self) -> None:
        first = self.good["predictions"][0]
        cases = {
            "missing": [first],
            "extra": [*self.good["predictions"], prediction(row("c", "cand-stop"), "cand-stop")],
            "duplicate": [first, first],
            "wrong gold": [{**first, "gold": "cand-stop"}, self.good["predictions"][1]],
            "unoffered": [{**first, "pred": "cand-other"}, self.good["predictions"][1]],
        }
        for name, predictions in cases.items():
            with self.subTest(name), self.assertRaises(SystemExit):
                evaluate.check({"predictions": predictions}, self.rows, name)

    def test_a_baseline_that_is_not_the_training_start_is_refused(self) -> None:
        run = {
            "parameter_fingerprints_before": {"lora": "a", "head": "b"},
            "version": "v",
            "records_sha256": "r",
        }
        base = {
            "fingerprints": {"lora": "a", "head": "b"},
            "same_start_as_training_run": True,
            "records_sha256": "r",
        }
        tuned = {
            "model": "v",
            "offline": True,
            "records_sha256": "r",
            "manifest_records_sha256": "r",
        }
        evaluate.accept(base, tuned, run, "r")
        for bad_base in (
            {**base, "same_start_as_training_run": False},
            {**base, "fingerprints": {"lora": "x", "head": "b"}},
            {**base, "records_sha256": "other"},
        ):
            with self.assertRaises(SystemExit):
                evaluate.accept(bad_base, tuned, run, "r")
        for bad_tuned in ({**tuned, "model": "w"}, {**tuned, "offline": False}):
            with self.assertRaises(SystemExit):
                evaluate.accept(base, bad_tuned, run, "r")

    def test_controlled_pairs_need_identical_words_and_different_evidence(self) -> None:
        same = [row("a", "cand-clarify", evidence=1), row("b", "cand-stop", evidence=2)]
        self.assertEqual(len(evaluate.controlled(same)), 1)
        reworded = [row("a", "cand-clarify", "Q1", 1), row("b", "cand-stop", "Q2", 2)]
        self.assertEqual(evaluate.controlled(reworded), [])
        identical_evidence = [row("a", "cand-clarify", "Q", 1), row("b", "cand-stop", "Q", 1)]
        self.assertEqual(evaluate.controlled(identical_evidence), [])

    def test_controlled_pairs_with_other_candidate_arguments_are_not_counted(self) -> None:
        a = row("a", "cand-clarify", evidence=1, arguments={"target_top": 5.0})
        b = row("b", "cand-stop", evidence=2, arguments={"target_top": 10.0})
        same = row("c", "cand-stop", evidence=3, arguments={"target_top": 5.0})
        self.assertEqual(evaluate.controlled([a, b]), [])
        self.assertEqual(
            [(x["id"], y["id"]) for x, y in evaluate.controlled([a, b, same])], [("a", "c")]
        )

    def test_controlled_predictions_must_be_on_the_evaluated_rows(self) -> None:
        run = {
            "parameter_fingerprints_before": {"lora": "a"},
            "version": "v",
            "records_sha256": "r",
        }
        extra = {"records_sha256": "r", "rows_sha256": "x"}
        base = {"fingerprints": {"lora": "a"}, "same_start_as_training_run": True, **extra}
        tuned = {"model": "v", "offline": True, "manifest_records_sha256": "r", **extra}
        evaluate.accept(base, tuned, run, "r", "x")
        for bad in ({**base, "rows_sha256": "y"}, {**base, "rows_sha256": None}):
            with self.assertRaises(SystemExit):
                evaluate.accept(bad, tuned, run, "r", "x")
        with self.assertRaises(SystemExit):
            evaluate.accept(base, {**tuned, "rows_sha256": "y"}, run, "r", "x")
        for bad_base in (
            {**base, "same_start_as_training_run": False},
            {**base, "fingerprints": {"lora": "z"}},
        ):
            with self.assertRaises(SystemExit):
                evaluate.accept(bad_base, tuned, run, "r", "x")
        with self.assertRaises(SystemExit):
            evaluate.accept(base, {**tuned, "offline": False}, run, "r", "x")
        with self.assertRaises(SystemExit):
            evaluate.accept(base, tuned, run, "r", None)

    def test_same_evidence_pairs_need_different_wording(self) -> None:
        pairs = [row("a", "cand-clarify", "Q1", 1), row("b", "cand-stop", "Q2", 1)]
        self.assertEqual(len(evaluate.same_evidence(pairs)), 1)
        self.assertEqual(
            evaluate.same_evidence([row("a", "cand-clarify"), row("b", "cand-stop")]), []
        )


if __name__ == "__main__":
    unittest.main()
