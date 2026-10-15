# Purpose: build real-data teaching records from frozen holes; developer-only, nothing is synthetic.
import argparse
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from hylogger_bridge.science import features
from hylogger_bridge.science.hole import Hole
from hylogger_bridge.science.package import read
from hylogger_bridge.science.request import STAGES, build
from training import rubric

PYTSG = "pytsg 1.0.0 @ 481f5faf6e1153791b849d4216a47f86f7db20ce"
Window = tuple[tuple[float, float], tuple[float, float]]


def retrievals(root: Path) -> dict[str, dict[str, Any]]:
    lines = (root / "retrieval.jsonl").read_text().splitlines()
    return {entry["file"]: entry for entry in map(json.loads, lines) if entry}


def windows(hole: Hole, length: int) -> list[Window]:
    """Consecutive target intervals, each with the interval of equal length directly above."""
    bottom = int(-(-max(hole.depth) // length)) * length
    return [
        ((float(top), float(top + length)), (float(top - length), float(top)))
        for top in range(length, bottom - length + 1, length)
    ]


def variants(rng: random.Random) -> list[tuple[str, str]]:
    """Two different (question kind, instruction stance) pairs for one unit of evidence."""
    first = (rng.choice(rubric.KINDS), rng.choice(rubric.STANCES))
    second = first
    while second == first:
        second = (rng.choice(rubric.KINDS), rng.choice(rubric.STANCES))
    return [first, second]


def unit(
    hole: Hole,
    family: str,
    split: str,
    source: dict[str, Any],
    window: Window,
    length: int,
    stage: str,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """One observed state with two different questions: same evidence, different intent."""
    target, reference = window
    span = {"t": f"{target[0]:g}-{target[1]:g} m", "r": f"{reference[0]:g}-{reference[1]:g} m"}
    rows = []
    for number, (kind, stance) in enumerate(variants(rng)):
        question = rng.choice(rubric.QUESTIONS[kind]).format(**span)
        instruction = rng.choice(rubric.INSTRUCTIONS[stance])
        request = build(hole, target, reference, stage, question, instruction)
        gold = rubric.choose(kind, stance, stage, rubric.observed(request["evidence"]))
        rows.append(
            {
                "id": f"r1-{hole.hole_id}-{target[0]:g}-{length}m-{stage}-{number}",
                "split": split,
                "group": family,
                "origin": "organiser",
                "provenance": {
                    **source,
                    "hole_id": hole.hole_id,
                    "target_m": list(target),
                    "reference_m": list(reference),
                    "tool_version": f"{PYTSG}; hylogger science {features.METHOD}",
                    "method_version": f"{features.METHOD}+{rubric.VERSION}",
                },
                "label_origin": "teaching_rule",
                "request": request,
                "gold": f"cand-{gold}",
                "meta": {"kind": kind, "stance": stance, "stage": stage, "window_m": length},
            }
        )
    return rows


def draw(
    hole: Hole, family: str, source: dict[str, Any], plan: dict[str, Any]
) -> list[list[dict[str, Any]]]:
    rng = random.Random(f"{plan['seed']}:{hole.hole_id}")
    split = plan["groups"][family]
    return [
        unit(hole, family, split, source, window, length, stage, rng)
        for length in plan["windows_m"]
        for window in windows(hole, length)
        for stage in STAGES
    ]


def stratified(
    units: list[list[dict[str, Any]]], count: int, rng: random.Random
) -> list[dict[str, Any]]:
    """Round-robin over (stage, first label) buckets of whole units, so rare labels survive."""
    buckets: dict[tuple[str, str], list[list[dict[str, Any]]]] = {}
    for item in units:
        buckets.setdefault((item[0]["meta"]["stage"], item[0]["gold"]), []).append(item)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    chosen: list[dict[str, Any]] = []
    while len(chosen) < count and any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key] and len(chosen) < count:
                chosen += buckets[key].pop()
    return chosen


def hole_entry(
    hole: Hole, name: str, family: str, split: str, source: dict[str, Any]
) -> dict[str, Any]:
    return {
        "hole_id": hole.hole_id,
        "package": name,
        "family": family,
        "split": split,
        "identity": dict(hole.identity),
        "spots": len(hole.depth),
        "depth_m": [min(hole.depth), max(hole.depth)],
        "valid_spots": sum(hole.valid),
        "swir_answers": sum(g is not None for g in hole.swir),
        "tir_answers": sum(g is not None for g in hole.tir),
        "extracted_files": dict(hole.files),
        **source,
    }


def build_all(config: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    plan = json.loads(config.read_text())
    root = Path(plan["root"])
    log = retrievals(root)
    pool: dict[str, list[list[dict[str, Any]]]] = {"train": [], "validation": [], "test": []}
    holes = []
    for name in plan["packages"]:
        got = log[name]
        archive = root / name
        if hashlib.sha256(archive.read_bytes()).hexdigest() != got["sha256"]:
            raise ValueError(f"{name} does not match its recorded SHA-256")
        hole = read(root / name.removesuffix(".zip") / "pkg", name.removesuffix(".zip"))
        match = re.match(r"[A-Za-z]+", hole.hole_id)
        if match is None or match[0] not in plan["groups"]:
            raise ValueError(f"{hole.hole_id} has no frozen family")
        family = match[0]
        source = {
            "source_url": got["url"],
            "source_sha256": got["sha256"],
            "retrieved_at": got["retrieved_at"],
            "licence": plan["licence"],
        }
        pool[plan["groups"][family]] += draw(hole, family, source, plan)
        holes.append(hole_entry(hole, name, family, plan["groups"][family], source))
    rng = random.Random(plan["seed"])
    rows = [r for split in pool for r in stratified(pool[split], plan["samples"][split], rng)]
    manifest = {
        "version": plan["version"],
        "rubric": rubric.VERSION,
        "method": features.METHOD,
        "pytsg": PYTSG,
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "excluded": plan["excluded"],
        "families_are_name_prefixes": "Official project membership is not verified.",
        "holes": holes,
        "available_units": {s: len(pool[s]) for s in pool},
        "records": {
            s: {
                "count": sum(r["split"] == s for r in rows),
                "by_label": dict(Counter(r["gold"] for r in rows if r["split"] == s)),
                "by_stage": dict(Counter(r["meta"]["stage"] for r in rows if r["split"] == s)),
                "families": sorted({r["group"] for r in rows if r["split"] == s}),
            }
            for s in pool
        },
        "sampling": (
            "Whole units (one observed state, two different questions) are drawn round-robin "
            "over (stage, label) buckets, so label shares are balanced, not natural."
        ),
        "label_origins": dict(Counter(r["label_origin"] for r in rows)),
        "limitations": [
            "Labels come from the teaching rubric, not expert review; no expert labels exist.",
            "Features are real measurements; the next-action labels are rules we wrote.",
            "Families are hole-name prefixes; official project independence is not verified.",
        ],
    }
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("training/real.json"))
    parser.add_argument("--out", type=Path, default=Path("data/decision/real-r1.jsonl"))
    args = parser.parse_args()
    rows, manifest = build_all(args.config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    manifest["records_sha256"] = hashlib.sha256(args.out.read_bytes()).hexdigest()
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["records"], indent=2))


if __name__ == "__main__":
    main()
