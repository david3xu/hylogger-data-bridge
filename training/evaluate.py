# Purpose: compare the untrained model, the trained model and baselines on the same test rows.
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from training import rubric
from training.records import load

ACTIONS = ["cand-qa_check", "cand-interval_compare", "cand-clarify", "cand-stop"]
TOLERANCE = 0.01
OK = {
    "target_positions": 5,
    "reference_positions": 5,
    "target_coverage": 1.0,
    "reference_coverage": 1.0,
    "target_valid": 1.0,
    "reference_valid": 1.0,
    "target_swir": 1.0,
    "reference_swir": 1.0,
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blind(row: dict[str, Any]) -> str:
    """The rubric with its numbers hidden: the same question logic, every interval assumed fine."""
    meta = row["meta"]
    return f"cand-{rubric.choose(meta['kind'], meta['stance'], meta['stage'], OK)}"


def rule(row: dict[str, Any]) -> str:
    meta, seen = row["meta"], rubric.observed(row["request"]["evidence"])
    return f"cand-{rubric.choose(meta['kind'], meta['stance'], meta['stage'], seen)}"


def check(value: dict[str, Any], rows: list[dict[str, Any]], what: str) -> dict[str, str]:
    """Exactly one valid prediction per expected row, or the comparison is refused."""
    ids = [p["id"] for p in value["predictions"]]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{what}: duplicate prediction IDs")
    expected = {r["id"]: r for r in rows}
    if set(ids) != set(expected):
        gone, extra = set(expected) - set(ids), set(ids) - set(expected)
        raise SystemExit(f"{what}: {len(gone)} rows missing and {len(extra)} unexpected")
    for p in value["predictions"]:
        row = expected[p["id"]]
        offered = {c["id"] for c in row["request"]["candidates"]}
        if p["gold"] != row["gold"] or p["pred"] not in offered or set(p["scores"]) != offered:
            raise SystemExit(f"{what}: prediction {p['id']} does not match its row")
        scores = p["scores"]
        for score in scores.values():
            number = isinstance(score, (int, float)) and not isinstance(score, bool)
            if not number or not math.isfinite(score) or not 0 <= score <= 1:
                raise SystemExit(f"{what}: prediction {p['id']} has an invalid probability")
        if abs(sum(scores.values()) - 1) > TOLERANCE:
            raise SystemExit(f"{what}: prediction {p['id']} probabilities do not sum to one")
        if scores[p["pred"]] < max(scores.values()) - 1e-9:
            raise SystemExit(f"{what}: prediction {p['id']} is not its highest-probability option")
    return {p["id"]: p["pred"] for p in value["predictions"]}


def accept(
    base: dict[str, Any],
    tuned: dict[str, Any],
    run: dict[str, Any],
    records: str,
    rows: str | None = None,
) -> None:
    """Refuse a comparison whose baseline is not the training run's own starting model.

    Evaluation-only rows must also be the very rows the predictions were made on (`rows`).
    """
    if base.get("fingerprints") != run["parameter_fingerprints_before"]:
        raise SystemExit("untrained baseline does not match the training run's starting parameters")
    if base.get("same_start_as_training_run") is not True:
        raise SystemExit("untrained baseline was not confirmed to match the training start")
    if tuned.get("model") != run["version"] or tuned.get("offline") is not True:
        raise SystemExit("trained predictions are not from the offline reload of the run's model")
    for name, value in (
        ("run", run["records_sha256"]),
        ("untrained", base.get("records_sha256")),
        ("trained", tuned.get("records_sha256")),
        ("trained manifest", tuned.get("manifest_records_sha256")),
    ):
        if value != records:
            raise SystemExit(f"{name} used different records than the ones being evaluated")
    for name, value in (
        ("untrained", base.get("rows_sha256")),
        ("trained", tuned.get("rows_sha256")),
    ):
        if value != rows:
            raise SystemExit(f"{name} predictions were not made on the rows being evaluated")


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


def separated(
    preds: dict[str, str], group: list[tuple[dict[str, Any], dict[str, Any]]]
) -> dict[str, Any]:
    both = sum(preds[a["id"]] == a["gold"] and preds[b["id"]] == b["gold"] for a, b in group)
    differ = sum(preds[a["id"]] != preds[b["id"]] for a, b in group)
    return {"pairs": len(group), "both_correct": both, "predictions_differ": differ}


def words(row: dict[str, Any]) -> tuple[str, str, str]:
    """Question, instruction and the complete candidate criteria, arguments included."""
    ask = row["request"]
    return ask["question"], ask["instruction"], json.dumps(ask["candidates"], sort_keys=True)


def grouped(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Label-changing pairs from the same stage, question kind and instruction stance.

    Not controlled: question wording and interval numbers differ between the two rows.
    """
    strata: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        m = r["meta"]
        strata[(m["stage"], m["kind"], m["stance"], r["request"]["instruction"])].append(r)
    return [
        (a, b) for g in strata.values() for a, b in combinations(g, 2) if a["gold"] != b["gold"]
    ]


def same_evidence(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pairs sharing identical observed evidence whose question or instruction text differs."""
    units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        units[json.dumps(r["request"]["evidence"], sort_keys=True)].append(r)
    pairs = [(a, b) for u in units.values() for a, b in combinations(u, 2)]
    return [
        (a, b)
        for a, b in pairs
        if a["gold"] != b["gold"] and words(a)[:2] != words(b)[:2] and words(a)[2] == words(b)[2]
    ]


def controlled(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pairs with literally the same question, instruction and action types but other evidence."""
    found = []
    for a, b in combinations(rows, 2):
        same_words = words(a) == words(b) and a["meta"]["stage"] == b["meta"]["stage"]
        other = a["request"]["evidence"] != b["request"]["evidence"]
        if same_words and other and a["gold"] != b["gold"]:
            found.append((a, b))
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--untrained", type=Path, required=True)
    parser.add_argument("--trained", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--controlled-rows", type=Path)
    parser.add_argument("--controlled-untrained", type=Path)
    parser.add_argument("--controlled-trained", type=Path)
    args = parser.parse_args()
    given = [args.controlled_rows, args.controlled_untrained, args.controlled_trained]
    if any(given) and not all(given):
        parser.error(
            "give --controlled-rows, --controlled-untrained and --controlled-trained together"
        )
    every = load(args.records)
    rows = [r for r in every if r["split"] == "test"]
    run = json.loads(args.run.read_text())
    base, tuned = json.loads(args.untrained.read_text()), json.loads(args.trained.read_text())
    accept(base, tuned, run, sha(args.records))
    train_labels = Counter(r["gold"] for r in every if r["split"] == "train")
    majority = train_labels.most_common(1)[0][0]
    by_question: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for r in every:
        if r["split"] == "train":
            m = r["meta"]
            by_question[(m["stage"], m["kind"], m["stance"])][r["gold"]] += 1
    fallback = {key: counts.most_common(1)[0][0] for key, counts in by_question.items()}
    models = {
        "untrained_model": check(base, rows, "untrained"),
        "trained_model": check(tuned, rows, "trained"),
        "teaching_rule": {r["id"]: rule(r) for r in rows},
        "rule_without_numbers": {r["id"]: blind(r) for r in rows},
        "train_majority_label": {r["id"]: majority for r in rows},
        "train_majority_per_stage_question": {
            r["id"]: fallback.get(
                (r["meta"]["stage"], r["meta"]["kind"], r["meta"]["stance"]), majority
            )
            for r in rows
        },
    }
    decisive = [r for r in rows if blind(r) != r["gold"]]
    names = ("untrained_model", "trained_model", "teaching_rule")
    report: dict[str, Any] = {
        "test_rows": len(rows),
        "test_label_counts": dict(Counter(r["gold"] for r in rows)),
        "test_families": sorted({r["group"] for r in rows}),
        "model_version": run["version"],
        "records_sha256": run["records_sha256"],
        "untrained_matches_training_start": True,
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
            "accuracy": {n: table(p, decisive)["accuracy"] for n, p in models.items()},
        },
        "sensitivity": {
            "same_evidence_different_question": {
                n: separated(models[n], same_evidence(rows)) for n in names
            },
            "grouped_label_changes_not_controlled": {
                n: separated(models[n], grouped(rows)) for n in names
            },
        },
        "caveat": "Labels are teaching-rule outputs; agreement is not usefulness.",
    }
    if args.controlled_rows:
        extra = [json.loads(x) for x in args.controlled_rows.read_text().splitlines() if x.strip()]
        a = json.loads(args.controlled_untrained.read_text())
        b = json.loads(args.controlled_trained.read_text())
        accept(a, b, run, sha(args.records), sha(args.controlled_rows))
        cmodels = {
            "untrained_model": check(a, extra, "controlled untrained"),
            "trained_model": check(b, extra, "controlled trained"),
            "teaching_rule": {r["id"]: rule(r) for r in extra},
        }
        pairs = controlled(extra)
        report["controlled_same_question_different_evidence"] = {
            "rows": len(extra),
            "rows_sha256": sha(args.controlled_rows),
            "label_counts": dict(Counter(r["gold"] for r in extra)),
            "accuracy": {n: table(p, extra)["accuracy"] for n, p in cmodels.items()},
            "supported_pairs": len(pairs),
            "pairs": {n: separated(p, pairs) for n, p in cmodels.items()},
        }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("test_rows", "by_stage", "sensitivity")}, indent=2))
    for name, value in report["models"].items():
        print(name, value["accuracy"], value["errors"])
    if "controlled_same_question_different_evidence" in report:
        print(json.dumps(report["controlled_same_question_different_evidence"], indent=2))


if __name__ == "__main__":
    main()
