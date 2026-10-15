# Purpose: the minimum coverage QA and interval comparison, calculated from measured spots.
import math
from collections import Counter

from hylogger_bridge.science.hole import Hole

METHOD = "qa-compare-2"
TIE = 1e-9

Features = dict[str, float | None]


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def bounds(top: float, bottom: float) -> None:
    """An interval is [top, bottom) with finite bounds and positive width."""
    if not (math.isfinite(top) and math.isfinite(bottom) and top < bottom):
        raise ValueError(f"interval bounds must be finite and increasing, got {top}, {bottom}")


def pitch(hole: Hole) -> float | None:
    """The package's own sampling step: the smallest gap between its distinct depths, if any.

    The smallest gap, not a typical one, so that missing positions never widen the step and hide
    their own gaps. Nothing here assumes a density; it is read from the package's depths.
    """
    depths = sorted(set(hole.depth))
    gaps = [b - a for a, b in zip(depths, depths[1:], strict=False)]
    return min(gaps) if gaps else None


def spots(hole: Hole, top: float, bottom: float) -> list[int]:
    """Spots whose depth lies in [top, bottom); repeated depths are separate spots."""
    bounds(top, bottom)
    return [i for i, depth in enumerate(hole.depth) if top <= depth < bottom]


def qa(hole: Hole, top: float, bottom: float) -> Features:
    """Row quality and depth coverage, kept apart.

    `valid_fraction` and the answer fractions describe the rows that exist. `coverage` is the
    share of the interval's expected sampling positions holding at least one clean spot, with
    the step taken from this package's own depths. An interval full of good rows in two
    positions out of ten has fractions of 1.0 and coverage 0.2.
    """
    found = spots(hole, top, bottom)
    clean = [i for i in found if hole.valid[i]]
    step = pitch(hole)
    expected = None if step is None else max(1, round((bottom - top) / step))
    held = len({hole.depth[i] for i in clean})
    return {
        "spots": len(found),
        "valid_fraction": _ratio(len(clean), len(found)),
        "expected_positions": expected,
        "coverage": None if expected is None else round(min(1.0, held / expected), 4),
        "swir_fraction": _ratio(sum(hole.swir[i] is not None for i in clean), len(clean)),
        "tir_fraction": _ratio(sum(hole.tir[i] is not None for i in clean), len(clean)),
    }


def _shares(hole: Hole, top: float, bottom: float) -> dict[str, float]:
    answers = [
        group
        for i in spots(hole, top, bottom)
        if hole.valid[i] and (group := hole.swir[i]) is not None
    ]
    return {group: n / len(answers) for group, n in Counter(answers).items()}


def leaders(shares: dict[str, float]) -> list[str]:
    """Every group sharing the highest share; more than one means no unique dominant group."""
    top = max(shares.values())
    return sorted(group for group, share in shares.items() if share >= top - TIE)


def compare(hole: Hole, target: tuple[float, float], reference: tuple[float, float]) -> Features:
    """Shift in SWIR group shares between two intervals, from clean, interpreted spots only.

    `group_shift` is the total variation distance (0 identical, 1 disjoint). `lead_changed` is
    1 or 0 only when both intervals have one unique dominant group; with a tie it is None and
    the leader counts say why. An interval with no answers gives None throughout.
    """
    a, b = _shares(hole, *target), _shares(hole, *reference)
    if not a or not b:
        return {
            "group_shift": None,
            "lead_changed": None,
            "target_leaders": len(leaders(a)) if a else None,
            "reference_leaders": len(leaders(b)) if b else None,
        }
    ours, theirs = leaders(a), leaders(b)
    shift = sum(abs(a.get(g, 0.0) - b.get(g, 0.0)) for g in a.keys() | b.keys()) / 2
    unique = len(ours) == 1 and len(theirs) == 1
    return {
        "group_shift": round(shift, 4),
        "lead_changed": int(ours != theirs) if unique else None,
        "target_leaders": len(ours),
        "reference_leaders": len(theirs),
    }
