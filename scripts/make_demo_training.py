# Purpose: generate explicitly synthetic state/action supervision for pipeline demonstration.
import argparse
import itertools
import json
from pathlib import Path

from hylogger_bridge.state import GOALS, State


def teaching_action(state: State) -> str:
    """A declared synthetic teacher, not geological ground truth or a runtime fallback."""
    allowed = state.allowed_actions()
    if len(allowed) == 1:
        return allowed[0]
    if "PRESENT_TO_EXPERT" in allowed:
        return "PRESENT_TO_EXPERT"
    if "PRESENT_PARTIAL" in allowed:
        return "PRESENT_PARTIAL"
    if state.goal == "compare_intervals":
        return "COMPARE_INTERVALS"
    if not state.changes_ready:
        return "DETECT_CHANGES"
    if state.assays_status == "not_loaded":
        return "GET_ASSAYS"
    return "CALCULATE_OVERLAP"


def generate(path: Path) -> None:
    records: list[dict[str, object]] = []
    for goal in GOALS:
        base = State.from_dict({"goal": goal})
        states = [base, State.from_dict({"goal": goal, "data_loaded": True})]
        states.append(State.from_dict({"goal": goal, "data_loaded": True, "qa_status": "failed"}))
        for changes, comparison, assays, overlap in itertools.product(
            (False, True), (False, True), ("not_loaded", "available", "unavailable"), (False, True)
        ):
            if overlap and (not changes or assays != "available"):
                continue
            states.append(
                State.from_dict(
                    {
                        "goal": goal,
                        "data_loaded": True,
                        "qa_status": "passed",
                        "changes_ready": changes,
                        "comparison_ready": comparison,
                        "assays_status": assays,
                        "overlap_ready": overlap,
                    }
                )
            )
        for state in states:
            # Include control examples at every stage; no raw geological data exist here.
            for control in (
                {},
                {"question_clear": False},
                {"budget_remaining": 0},
                {"tool_failure": True},
                {"cancelled": True},
            ):
                variant = State.from_dict(state.to_dict() | control)
                records.append({"state": variant.to_dict(), "action": teaching_action(variant)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "origin": "synthetic",
                "description": "Enumerated workflow states labelled by a declared teaching policy; "
                "not expert trajectories or geological validation.",
                "records": records,
            },
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    generate(parser.parse_args().out)


if __name__ == "__main__":
    main()
