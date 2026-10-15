# Purpose: build evaluation-only rows from held-out measurements with one fixed question.
import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

from hylogger_bridge.science.package import read
from hylogger_bridge.science.request import build
from training import rubric
from training.real import windows

QUESTION = "Does the dominant SWIR mineral group change between the reference and target intervals?"


def rows(config: Path, per_stage: int, seed: int) -> list[dict[str, Any]]:
    """The same words for every row, so only the measured evidence differs between rows.

    Only holes of the frozen test families are used, and nothing here touches training rows.
    """
    plan = json.loads(config.read_text())
    root = Path(plan["root"])
    pool: dict[str, list[dict[str, Any]]] = {"qa": [], "compare": []}
    for name in plan["packages"]:
        hole = read(root / name.removesuffix(".zip") / "pkg", name.removesuffix(".zip"))
        family = re.match(r"[A-Za-z]+", hole.hole_id)
        if family is None or plan["groups"].get(family[0]) != "test":
            continue
        for target, reference in windows(hole, 5):
            for stage in pool:
                ask = build(hole, target, reference, stage, QUESTION, "")
                gold = rubric.choose("difference", "none", stage, rubric.observed(ask["evidence"]))
                pool[stage].append(
                    {
                        "id": f"ctl-{hole.hole_id}-{target[0]:g}-{stage}",
                        "split": "controlled",
                        "group": hole.hole_id,
                        "gold": f"cand-{gold}",
                        "request": ask,
                        "meta": {
                            "kind": "difference",
                            "stance": "none",
                            "stage": stage,
                            "window_m": 5,
                        },
                    }
                )
    rng = random.Random(seed)
    chosen: list[dict[str, Any]] = []
    for items in pool.values():
        # Rows share candidate criteria only when they share interval numbers, so group by them.
        shared: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            shared.setdefault(json.dumps(item["request"]["candidates"], sort_keys=True), []).append(
                item
            )
        useful = [g for g in shared.values() if len({r["gold"] for r in g}) > 1]
        rng.shuffle(useful)
        taken = 0
        for group in useful:
            if taken >= per_stage:
                break
            chosen += group
            taken += len(group)
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("training/real.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-stage", type=int, default=30)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    built = rows(args.config, args.per_stage, args.seed)
    args.out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in built))
    labels: dict[str, int] = {}
    for r in built:
        key = f"{r['meta']['stage']}/{r['gold']}"
        labels[key] = labels.get(key, 0) + 1
    print(len(built), "rows", labels)


if __name__ == "__main__":
    main()
