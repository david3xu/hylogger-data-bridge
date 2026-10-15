# Purpose: build the assessment request for an interval comparison; training and runtime share it.
from typing import Any

from hylogger_bridge.science.features import Features, compare, qa
from hylogger_bridge.science.hole import Hole

FAMILY = "interval-comparison-1"
STAGES = ("inventory", "qa", "compare")
KINDS = {"inventory": "observation", "qa": "calculation", "compare": "calculation"}
ACTIONS = ("qa_check", "interval_compare", "clarify", "stop")
CALCULATIONS = ("qa_check", "interval_compare")

Interval = tuple[float, float]


def page_id(hole: Hole, target: Interval) -> str:
    return f"{hole.hole_id}:{target[0]:g}-{target[1]:g}m"


def candidates(target: Interval, reference: Interval) -> list[dict[str, Any]]:
    """Only actions this package can really support: two calculations, and two non-calculations."""
    where = {
        "target_top": target[0],
        "target_bottom": target[1],
        "reference_top": reference[0],
        "reference_bottom": reference[1],
    }
    return [
        {
            "id": f"cand-{name}",
            "action_type": name,
            "arguments": where if name in CALCULATIONS else {},
        }
        for name in ACTIONS
    ]


def measured(hole: Hole, target: Interval, reference: Interval) -> dict[str, Features]:
    """Every feature this family knows, by evidence ID. Callers choose which are observed so far."""
    a, b = qa(hole, *target), qa(hole, *reference)
    return {
        "inventory": {
            "target_spots": a["spots"],
            "reference_spots": b["spots"],
            "target_positions": a["expected_positions"],
            "reference_positions": b["expected_positions"],
        },
        "qa": {
            "target_valid": a["valid_fraction"],
            "reference_valid": b["valid_fraction"],
            "target_coverage": a["coverage"],
            "reference_coverage": b["coverage"],
            "target_swir": a["swir_fraction"],
            "reference_swir": b["swir_fraction"],
        },
        "compare": compare(hole, target, reference),
    }


def evidence(hole: Hole, target: Interval, reference: Interval, stage: str) -> list[dict[str, Any]]:
    """Everything observed before the next action, and nothing that action would reveal."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage}")
    known = measured(hole, target, reference)
    return [
        {"evidence_id": key, "kind": KINDS[key], "state": "complete", "features": known[key]}
        for key in STAGES[: STAGES.index(stage) + 1]
    ]


def build(
    hole: Hole, target: Interval, reference: Interval, stage: str, question: str, instruction: str
) -> dict[str, Any]:
    return {
        "contract_version": 1,
        "page_id": page_id(hole, target),
        "state_revision": STAGES.index(stage),
        "question": question,
        "instruction": instruction,
        "evidence": evidence(hole, target, reference, stage),
        "candidates": candidates(target, reference),
    }
