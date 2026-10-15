# Purpose: human-readable descriptions of scientific evidence (inventory, QA, and comparison).
from collections import Counter
from typing import Any

from hylogger_bridge.science import features
from hylogger_bridge.science.hole import Hole

LABELS = {
    "inventory": "Scientific inventory",
    "qa": "Scientific qa",
    "compare": "Scientific compare",
}


def _interval_qa(hole: Hole, top: float, bottom: float) -> tuple[str, str, str]:
    found = features.spots(hole, top, bottom)
    total_spots = len(found)
    clean = [i for i in found if hole.valid[i]]
    n_valid = len(clean)
    valid_pct = f"{100 * n_valid / total_spots:.1f}%" if total_spots > 0 else "0.0%"
    valid_str = f"{n_valid}/{total_spots} ({valid_pct})"

    grid = features.lattice(hole)
    if grid is not None:
        want = features.expected(grid, top, bottom)
        if want > 0:
            held = len({hole.depth[i] for i in clean})
            cov_pct = f"{100 * min(1.0, held / want):.1f}%"
            cov_str = f"{held}/{want} ({cov_pct})"
        else:
            cov_str = "coverage unknown"
    else:
        cov_str = "coverage unknown"

    swir_clean = sum(hole.swir[i] is not None for i in clean)
    swir_pct = f"{100 * swir_clean / n_valid:.1f}%" if n_valid > 0 else "0.0%"
    swir_str = f"{swir_clean}/{n_valid} ({swir_pct})"

    return valid_str, cov_str, swir_str


def _interval_groups(hole: Hole, top: float, bottom: float) -> str:
    found = features.spots(hole, top, bottom)
    answers = [group for i in found if hole.valid[i] and (group := hole.swir[i]) is not None]
    if not answers:
        return "none"
    counts = Counter(answers)
    total = len(answers)
    order = sorted(counts.items(), key=lambda item: (-item[1] / total, item[0]))
    parts = [f"{group} {n}/{total} ({100 * n / total:.1f}%)" for group, n in order]
    return ", ".join(parts)


def describe(
    hole: Hole,
    target: tuple[float, float],
    reference: tuple[float, float],
    stage: str,
    values: dict[str, Any],
) -> tuple[str, str]:
    """Pure function producing readable label and value for scientific evidence stages.

    Recomputes display counts from the Hole using features.py helpers without modifying values.
    """
    if stage not in LABELS:
        raise ValueError(f"unknown stage {stage}")

    label = LABELS[stage]

    if stage == "inventory":
        grid = features.lattice(hole)
        ref_spots_list = features.spots(hole, *reference)
        tgt_spots_list = features.spots(hole, *target)
        ref_n = len(ref_spots_list)
        tgt_n = len(tgt_spots_list)

        if grid is not None:
            ref_pos = f"{features.expected(grid, *reference)} expected grid positions"
            tgt_pos = f"{features.expected(grid, *target)} expected grid positions"
        else:
            ref_pos = "irregular grid"
            tgt_pos = "irregular grid"

        value = (
            f"Hole {hole.hole_id}. "
            f"Reference {reference[0]:g}–{reference[1]:g} m: {ref_n} spots ({ref_pos}). "
            f"Target {target[0]:g}–{target[1]:g} m: {tgt_n} spots ({tgt_pos})."
        )
        return label, value[:4000]

    elif stage == "qa":
        ref_valid, ref_cov, ref_swir = _interval_qa(hole, *reference)
        tgt_valid, tgt_cov, tgt_swir = _interval_qa(hole, *target)
        method_sentence = (
            "Method: clean spots only (TSG Final Mask); "
            "unmasked spots and non-interpretations "
            "(INVALID, ASPECTRAL, NOTAROK, empty) are excluded."
        )
        value = (
            f"Reference {reference[0]:g}–{reference[1]:g} m: "
            f"valid spots {ref_valid}; covered grid positions {ref_cov}; "
            f"valid spots with a SWIR group {ref_swir}. "
            f"Target {target[0]:g}–{target[1]:g} m: "
            f"valid spots {tgt_valid}; covered grid positions {tgt_cov}; "
            f"valid spots with a SWIR group {tgt_swir}. "
            f"{method_sentence}"
        )
        return label, value[:4000]

    elif stage == "compare":
        ref_groups = _interval_groups(hole, *reference)
        tgt_groups = _interval_groups(hole, *target)

        group_shift = values.get("group_shift")
        if group_shift is not None:
            shift_str = (
                f"group_shift = {group_shift:g} "
                "(total variation distance: 0 identical, 1 completely different)"
            )
        else:
            shift_str = (
                "group_shift = None (total variation distance: 0 identical, 1 completely different)"
            )

        lead_changed = values.get("lead_changed")
        tgt_leaders = values.get("target_leaders")
        ref_leaders = values.get("reference_leaders")
        leaders_detail = f"target leaders: {tgt_leaders}, reference leaders: {ref_leaders}"

        if lead_changed == 1:
            lead_str = f"lead_changed = 1 (changed; {leaders_detail})"
        elif lead_changed == 0:
            lead_str = f"lead_changed = 0 (unchanged; {leaders_detail})"
        else:
            if not tgt_leaders or not ref_leaders:
                lead_str = f"lead_changed = None (no answers; {leaders_detail})"
            else:
                lead_str = f"lead_changed = None (tie; {leaders_detail})"

        value = (
            f"Reference {reference[0]:g}–{reference[1]:g} m: {ref_groups}. "
            f"Target {target[0]:g}–{target[1]:g} m: {tgt_groups} "
            f"(TSG Grp1 sTSAS interpretations, not new mineral identification). "
            f"{shift_str}; {lead_str}."
        )
        return label, value[:4000]

    raise ValueError(f"unsupported stage: {stage}")
