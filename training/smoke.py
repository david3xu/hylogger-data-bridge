# Purpose: generate explicitly synthetic teaching cases for the portability check only.
import argparse
import json
import random
from pathlib import Path
from typing import Any


def records() -> list[dict[str, Any]]:
    rng = random.Random(3407)
    rows = []
    cases = [
        (
            "Check whether removing masked samples changes the comparison.",
            "Run the mask-sensitivity check before presenting.",
            "qa_check",
        ),
        (
            "Compare the selected interval with the section above.",
            "Use the already checked valid samples.",
            "interval_compare",
        ),
        (
            "Compare it with the other interval.",
            "The comparison interval has not been specified; ask me for its depths.",
            "clarify",
        ),
        (
            "Present the completed comparison and its limitations.",
            "The requested valid-sample comparison is complete; no additional analysis requested.",
            "stop",
        ),
        (
            "Calculate how much of the selected candidate overlaps the loaded assay intervals.",
            "Depth alignment and valid coverage are checked; the overlap calculation is pending.",
            "overlap_check",
        ),
    ]
    for group in range(12):
        split = "train" if group < 8 else "validation" if group < 10 else "test"
        for index, (question, instruction, action) in enumerate(cases):
            choices = [
                {"id": f"cand-{a}", "action_type": a, "arguments": {}}
                for a in ("qa_check", "interval_compare", "clarify", "stop", "overlap_check")
            ]
            rng.shuffle(choices)
            rows.append(
                {
                    "id": f"synthetic-{group}-{index}",
                    "group": f"synthetic-case-{group}",
                    "split": split,
                    "origin": "synthetic",
                    "label_origin": "teaching_rule",
                    "gold": f"cand-{action}",
                    "request": {
                        "contract_version": 1,
                        "page_id": f"page-{group}",
                        "state_revision": 1,
                        "question": question,
                        "instruction": instruction,
                        "evidence": [
                            {
                                "evidence_id": f"synthetic-evidence-{group}",
                                "kind": "calculation",
                                "state": "complete",
                                "features": {
                                    "valid_count": 60 + group,
                                    "coverage_fraction": 0.8 + group / 100,
                                    "mask_checked": 0 if index == 0 else 1,
                                    "comparison_done": 1 if index == 3 else 0,
                                    "assays_loaded": 1 if index == 4 else 0,
                                },
                            }
                        ],
                        "candidates": choices,
                    },
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row) + "\n" for row in records()))
    print(f"Wrote {len(records())} synthetic portability records; no geological evaluation.")


if __name__ == "__main__":
    main()
