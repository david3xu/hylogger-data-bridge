# Purpose: compare the saved model's offline reload with the predictions made in memory at training.
import argparse
import json
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.encode import encode


def parity(
    run: dict[str, Any], trained: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Every in-memory reference answer against the reload's, matched by identical request."""
    by_request = {json.dumps(r["request"], sort_keys=True): r["id"] for r in rows}
    reloaded = {p["id"]: p for p in trained["predictions"]}
    worst, differing, matched = 0.0, [], 0
    for ref in run["reference"]:
        row_id = by_request.get(json.dumps(ref["request"], sort_keys=True))
        if row_id is None or row_id not in reloaded:
            raise SystemExit("a training reference request has no matching reloaded prediction")
        _, _, mapping = encode(ref["request"])
        said = ref["answers"]["follow_up"]
        mine = reloaded[row_id]
        matched += 1
        for option, value in said["probabilities"].items():
            worst = max(worst, abs(value - mine["scores"][mapping[option]]))
        if mapping[said["answer"]] != mine["pred"]:
            differing.append(row_id)
    if matched != len(rows) or len(reloaded) != len(rows):
        raise SystemExit("reference and reload do not cover exactly the evaluated rows")
    return {
        "rows": matched,
        "max_probability_difference": round(worst, 6),
        "answers_that_differ": differing,
        "model": run["version"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--trained", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from training.records import load

    rows = [r for r in load(args.records) if r["split"] == "test"]
    report = parity(json.loads(args.run.read_text()), json.loads(args.trained.read_text()), rows)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
