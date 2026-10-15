# Purpose: compare the untrained model, the trained model and simple baselines on the same test rows.
import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from training import rubric
from training.records import load

ACTIONS = ["cand-qa_check", "cand-interval_compare", "cand-clarify", "cand-stop"]


def blind(row: dict[str, Any]) -> str:
    """The rubric with its numbers hidden: the same question logic, every interval assumed fine."""
    meta = row["meta"]
    ok = {
        "target_positions": 5,
        "reference_positions": 5,
        "target_coverage": 1.0,
        "reference_coverage": 1.0,
        "target_valid": 1.0,
        "reference_valid": 1.0,
        "target_swir": 1.0,
        "reference_swir": 1.0,
    }
    return f"cand-{rubric.choose(meta['kind'], meta['stance'], meta['stage'], ok)}"


def rule(row: dict[str, Any]) -> str:
    meta, seen = row["meta"], rubric.observed(row["request"]["evidence"])
    return f"cand-{rubric.choose(meta['kind'], meta['stance'], meta['stage'], seen)}"


def table(preds: dict[str, str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    hits = sum(preds[r["id"]] == r["gold"] for r in rows)
    per = {}
    for action in ACTIONS:
        support = [r for r in rows if r["gold"] == action]
        called = [r for r in rows if preds[r["id"]] == action]
        right = sum(preds[r["id"]] == action for r in support)
        per[action] = {
            "support": len(support),
            "predicted": len(called),
            "correct": right,
            "recall": round(right / len(support), 4) if support else None,
            "precision": round(right / len(called), 4) if called else None,
        }
    confusion = Counter((r["gold"], preds[r["id"]]) for r in rows if preds[r["id"]] != r["gold"])
    return {
        "accuracy": round(hits / len(rows), 4),
        "correct": hits,
        "rows": len(rows),
        "per_action": per,
        "errors": {f"{g} -> {p}": n for (g, p), n in confusion.most_common()},
    }


def pairs(preds: dict[str, str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Sensitivity: does the prediction change when evidence, or the question, changes the label?"""
    units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        units[r["id"].rsplit("-", 1)[0]].append(r)
    same_evidence = [(a, b) for u in units.values() for a, b in combinations(u, 2)]
    asked = [(a, b) for a, b in same_evidence if a["gold"] != b["gold"]]
    strata: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        m = r["meta"]
        strata[(m["stage"], m["kind"], m["stance"], r["request"]["instruction"])].append(r)
    flipped = [(a, b) for g in strata.values() for a, b in combinations(g, 2) if a["gold"] != b["gold"]]

    def separated(group: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
        both = sum(preds[a["id"]] == a["gold"] and preds[b["id"]] == b["gold"] for a, b in group)
        differ = sum(preds[a["id"]] != preds[b["id"]] for a, b in group)
        return {"pairs": len(group), "both_correct": both, "predictions_differ": differ}

    return {
        "same_evidence_different_question": separated(asked),
        "same_question_different_evidence": separated(flipped),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--untrained", type=Path, required=True)
    parser.add_argument("--trained", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    every = load(args.records)
    rows = [r for r in every if r["split"] == "test"]
    base, tuned = json.loads(args.untrained.read_text()), json.loads(args.trained.read_text())
    train_labels = Counter(r["gold"] for r in every if r["split"] == "train")
    majority = train_labels.most_common(1)[0][0]
    by_question: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for r in every:
        if r["split"] == "train":
            m = r["meta"]
            by_question[(m["stage"], m["kind"], m["stance"])][r["gold"]] += 1
    fallback = {
        key: counts.most_common(1)[0][0] for key, counts in by_question.items()
    }
    models = {
        "untrained_model": {p["id"]: p["pred"] for p in base["predictions"]},
        "trained_model": {p["id"]: p["pred"] for p in tuned["predictions"]},
        "teaching_rule": {r["id"]: rule(r) for r in rows},
        "rule_without_numbers": {r["id"]: blind(r) for r in rows},
        "train_majority_label": {r["id"]: majority for r in rows},
        "train_majority_per_stage_question": {
            r["id"]: fallback.get((r["meta"]["stage"], r["meta"]["kind"], r["meta"]["stance"]), majority)
            for r in rows
        },
    }
    decisive = [r for r in rows if blind(r) != r["gold"]]
    report: dict[str, Any] = {
        "test_rows": len(rows),
        "test_label_counts": dict(Counter(r["gold"] for r in rows)),
        "test_families": sorted({r["group"] for r in rows}),
        "untrained_matches_training_start": base.get("same_start_as_training_run"),
        "models": {name: table(preds, rows) for name, preds in models.items()},
        "by_stage": {
            stage: {
                name: table(preds, [r for r in rows if r["meta"]["stage"] == stage])["accuracy"]
                for name, preds in models.items()
            }
            for stage in ("inventory", "qa", "compare")
        },
        "numbers_decisive_rows": {
            "rows": len(decisive),
            "accuracy": {name: table(preds, decisive)["accuracy"] for name, preds in models.items()},
        },
        "sensitivity": {name: pairs(models[name], rows) for name in ("untrained_model", "trained_model", "teaching_rule")},
        "caveat": "Labels are teaching-rule outputs. Agreement with them shows the rubric was learned, not geological usefulness.",
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("test_rows", "by_stage", "numbers_decisive_rows")}, indent=2))
    for name, value in report["models"].items():
        print(name, value["accuracy"], value["errors"])


if __name__ == "__main__":
    main()
