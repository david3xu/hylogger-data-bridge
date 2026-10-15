# Purpose: the versioned teaching rubric for interval comparison, kept as a baseline too.
from typing import Any

VERSION = "teach-2"
KINDS = ("coverage", "difference", "summary")
STANCES = ("none", "check_first", "direct")
# Workflow rules we chose, not geology: an interval needs at least two sampling positions to be
# compared with anything, and both intervals need mostly clean, mostly interpreted coverage.
MIN_POSITIONS = 2
MIN_COVERAGE = 0.8
MIN_VALID = 0.6
MIN_ANSWERED = 0.6

QUESTIONS = {
    "coverage": (
        "Is there enough clean, interpreted spectral coverage to compare {t} with {r}?",
        "Can {t} be assessed against {r} with the measurements we have?",
    ),
    "difference": (
        "Does the dominant SWIR mineral group change between {r} and {t}?",
        "Is {t} mineralogically different from {r}?",
    ),
    "summary": (
        "Summarise how {t} relates to {r}.",
        "What can we say about {t} compared with {r}?",
    ),
}
INSTRUCTIONS = {
    "none": ("",),
    "check_first": ("Check data quality before comparing.", "Verify the coverage first."),
    "direct": ("Compare directly; I will judge data quality.", "Skip the quality check."),
}


def observed(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """The numbers already in the request, merged; later evidence never overrides earlier."""
    merged: dict[str, Any] = {}
    for item in evidence:
        merged.update(item["features"])
    return merged


def adequate(features: dict[str, Any]) -> bool:
    """Both intervals have depth coverage, mostly clean rows and mostly interpreted spots."""
    wanted = (
        ("target_coverage", MIN_COVERAGE),
        ("reference_coverage", MIN_COVERAGE),
        ("target_valid", MIN_VALID),
        ("reference_valid", MIN_VALID),
        ("target_swir", MIN_ANSWERED),
        ("reference_swir", MIN_ANSWERED),
    )
    return all(features.get(key) is not None and features[key] >= bar for key, bar in wanted)


def choose(kind: str, stance: str, stage: str, features: dict[str, Any]) -> str:
    """The teaching label: what a careful analyst would do next, by these stated rules.

    These are rules we wrote, not expert judgement. An explicit committed instruction is honoured
    when it names a supported step; otherwise checks come before the comparison they support.
    """
    positions = (features.get("target_positions"), features.get("reference_positions"))
    if any(p is None or p < MIN_POSITIONS for p in positions):
        return "clarify"
    if stage == "inventory":
        return "interval_compare" if stance == "direct" and kind != "coverage" else "qa_check"
    if stage == "qa":
        if kind == "coverage":
            return "stop"
        return "interval_compare" if adequate(features) else "clarify"
    return "stop" if adequate(features) else "clarify"
