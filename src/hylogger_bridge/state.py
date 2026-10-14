# Purpose: validate compact investigation states and enforce action prerequisites.
from dataclasses import asdict, dataclass, fields
from typing import Literal, cast

type Goal = Literal["changes_with_assays", "compare_intervals", "assess_quality"]
GOALS = ("changes_with_assays", "compare_intervals", "assess_quality")
ACTIONS = (
    "LOAD_DATA",
    "RUN_QA",
    "DETECT_CHANGES",
    "GET_ASSAYS",
    "CALCULATE_OVERLAP",
    "COMPARE_INTERVALS",
    "PRESENT_TO_EXPERT",
    "PRESENT_PARTIAL",
    "ASK_EXPERT",
    "STOP",
)


@dataclass(frozen=True)
class State:
    goal: Goal
    data_loaded: bool = False
    qa_status: str = "not_run"
    changes_ready: bool = False
    comparison_ready: bool = False
    assays_status: str = "not_loaded"
    overlap_ready: bool = False
    question_clear: bool = True
    budget_remaining: int = 10
    tool_failure: bool = False
    cancelled: bool = False

    @classmethod
    def from_dict(cls, value: object) -> "State":
        if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
            raise ValueError("state must be an object with string keys")
        names = {field.name for field in fields(cls)}
        if set(value) - names or "goal" not in value:
            raise ValueError("state requires goal and only documented fields")
        if value["goal"] not in GOALS:
            raise ValueError("unsupported goal")
        bool_fields = (
            "data_loaded",
            "changes_ready",
            "comparison_ready",
            "overlap_ready",
            "question_clear",
            "tool_failure",
            "cancelled",
        )
        for name in bool_fields:
            if name in value and type(value[name]) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if "budget_remaining" in value and (
            type(value["budget_remaining"]) is not int or value["budget_remaining"] < 0
        ):
            raise ValueError("budget_remaining must be a nonnegative integer")
        state = cls(**value)
        if state.qa_status not in ("not_run", "passed", "failed"):
            raise ValueError("invalid qa_status")
        if state.assays_status not in ("not_loaded", "available", "unavailable"):
            raise ValueError("invalid assays_status")
        if not state.data_loaded and (
            state.qa_status != "not_run" or state.assays_status != "not_loaded"
        ):
            raise ValueError("results cannot precede data loading")
        if (state.changes_ready or state.comparison_ready or state.overlap_ready) and (
            state.qa_status != "passed"
        ):
            raise ValueError("analysis results require passed QA")
        if state.overlap_ready and (not state.changes_ready or state.assays_status != "available"):
            raise ValueError("overlap requires candidates and available assays")
        return state

    def to_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))

    def allowed_actions(self) -> tuple[str, ...]:
        # Controls and prerequisites are enforced independently of learned weights.
        if self.cancelled or self.budget_remaining == 0 or self.tool_failure:
            return ("STOP",)
        if not self.question_clear:
            return ("ASK_EXPERT",)
        if not self.data_loaded:
            return ("LOAD_DATA",)
        if self.qa_status == "not_run":
            return ("RUN_QA",)
        if self.qa_status == "failed":
            return ("ASK_EXPERT",)
        allowed = ["ASK_EXPERT"]
        if not self.changes_ready:
            allowed.append("DETECT_CHANGES")
        if not self.comparison_ready:
            allowed.append("COMPARE_INTERVALS")
        if self.assays_status == "not_loaded":
            allowed.append("GET_ASSAYS")
        if self.changes_ready and self.assays_status == "available" and not self.overlap_ready:
            allowed.append("CALCULATE_OVERLAP")
        complete = (
            self.goal == "assess_quality"
            or (self.goal == "compare_intervals" and self.comparison_ready)
            or (self.goal == "changes_with_assays" and self.overlap_ready)
        )
        if complete:
            allowed.append("PRESENT_TO_EXPERT")
        if (
            self.goal == "changes_with_assays"
            and self.changes_ready
            and self.assays_status == "unavailable"
        ):
            allowed.append("PRESENT_PARTIAL")
        return tuple(allowed)


FEATURES = (
    *[f"goal={goal}" for goal in GOALS],
    "data_loaded",
    "qa_passed",
    "qa_failed",
    "changes_ready",
    "comparison_ready",
    "assays_available",
    "assays_unavailable",
    "overlap_ready",
    "question_clear",
    "budget_exhausted",
    "tool_failure",
    "cancelled",
)


def encode(state: State) -> list[float]:
    """Fixed binary features; no fitted preprocessing or geological measurements."""
    return [
        float(value)
        for value in (
            *[state.goal == goal for goal in GOALS],
            state.data_loaded,
            state.qa_status == "passed",
            state.qa_status == "failed",
            state.changes_ready,
            state.comparison_ready,
            state.assays_status == "available",
            state.assays_status == "unavailable",
            state.overlap_ready,
            state.question_clear,
            state.budget_remaining == 0,
            state.tool_failure,
            state.cancelled,
        )
    ]
