# Purpose: the minimum coverage QA and interval comparison, calculated from measured spots.
import math
from collections import Counter

from hylogger_bridge.science.hole import Hole

METHOD = "qa-compare-3"
TIE = 1e-9

Features = dict[str, float | None]


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def bounds(top: float, bottom: float) -> None:
    """An interval is [top, bottom) with finite bounds and positive width."""
    if not (math.isfinite(top) and math.isfinite(bottom) and top < bottom):
        raise ValueError(f"interval bounds must be finite and increasing, got {top}, {bottom}")


def lattice(hole: Hole) -> tuple[float, float] | None:
    """The package's own regular sampling grid as (origin, step), or None if it has none.

    The step is the smallest gap between distinct depths, so missing positions never widen it,
    and the grid is accepted only if every depth lies on it. Nothing assumes a density; an
    irregular or single-depth package has no grid and so no expected positions.
    """
    depths = sorted(set(hole.depth))
    gaps = [b - a for a, b in zip(depths, depths[1:], strict=False)]
    if not gaps:
        return None
    step, origin = min(gaps), depths[0]
    if any(
        abs(origin + round((d - origin) / step) * step - d) > 1e-6 * max(1.0, step) for d in depths
    ):
        return None
    return origin, step


def expected(grid: tuple[float, float], top: float, bottom: float) -> int:
    """How many grid positions fall in [top, bottom), by phase, not by width alone."""
    origin, step = grid
    first = math.ceil((top - origin) / step - 1e-9)
    last = math.ceil((bottom - origin) / step - 1e-9) - 1
    return max(0, last - first + 1)


def spots(hole: Hole, top: float, bottom: float) -> list[int]:
    """Spots whose depth lies in [top, bottom); repeated depths are separate spots."""
    bounds(top, bottom)
    return [i for i, depth in enumerate(hole.depth) if top <= depth < bottom]


def qa(hole: Hole, top: float, bottom: float) -> Features:
    """Row quality and depth coverage, kept apart.

    `valid_fraction` and the answer fractions describe the rows that exist. `coverage` is the
    share of the interval's expected grid positions holding at least one clean spot. An interval
    full of good rows in two positions out of ten has fractions of 1.0 and coverage 0.2. With no
    regular grid, or no grid position inside the interval, coverage is unknown (None).
    """
    found = spots(hole, top, bottom)
    clean = [i for i in found if hole.valid[i]]
    grid = lattice(hole)
    want = None if grid is None else expected(grid, top, bottom)
    held = len({hole.depth[i] for i in clean})
    return {
        "spots": len(found),
        "valid_fraction": _ratio(len(clean), len(found)),
        "expected_positions": want,
        "coverage": round(min(1.0, held / want), 4) if want else None,
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
