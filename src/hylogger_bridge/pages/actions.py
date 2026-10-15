# Purpose: the registered action types; validity here never depends on model advice.
from typing import Any

REGISTERED = frozenset({"qa_check", "overlap_check", "interval_compare", "clarify", "stop"})


def check(action: dict[str, Any], page: dict[str, Any]) -> None:
    """An action stands on its own: registered, and any advice it cites is recorded on the page."""
    if action["type"] not in REGISTERED:
        raise ValueError(f"unregistered action type {action['type']}")
    advice = action["assessment_id"]
    if advice is not None and (page["assessment"] is None or page["assessment"]["id"] != advice):
        raise ValueError("the consulted assessment is not recorded on this page")
