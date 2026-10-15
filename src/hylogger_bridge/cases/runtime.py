# Purpose: runtime application logic for preparing and continuing real-data cases.
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from hylogger_bridge.book import BookStore
from hylogger_bridge.pages.live import start as live_start
from hylogger_bridge.science import features
from hylogger_bridge.science.package import name_of
from hylogger_bridge.science.request import STAGES
from hylogger_bridge.store import scenes

WORKER = {"kind": "agent", "name": "r1-science-worker"}
SCIENTIFIC_LIMITS = (
    "No assay or assay-overlap result is used or claimed; "
    "measurements are TSG interpretations only."
)
LIMITS = SCIENTIFIC_LIMITS


def working(snapshot: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = next(
        p for p in snapshot["pages"] if p["id"] == snapshot["current_page_id"]
    )
    return page


def scene_of(book: Path, page_id: str | None) -> dict[str, Any]:
    with sqlite3.connect(book) as connection:
        if page_id is not None:
            scene = scenes.get(connection, page_id)
            if scene is not None:
                found: dict[str, Any] = scene
                return found
            # Walk up ancestor pages using the book's pages array
            row = connection.execute("SELECT data FROM book WHERE id=1").fetchone()
            if row is not None:
                book_data = json.loads(row[0])
                pages_by_id = {p["id"]: p for p in book_data.get("pages", [])}
                curr: str | None = page_id
                while curr is not None and curr in pages_by_id:
                    s = scenes.get(connection, curr)
                    if s is not None:
                        found_s: dict[str, Any] = s
                        return found_s
                    curr = pages_by_id[curr].get("parent_id")
    raise ValueError(f"No scientific scene found for page {page_id} or its ancestors")


def hole_depth_range(hole: Any) -> tuple[float, float]:
    grid = features.lattice(hole)
    if grid is not None:
        origin, step = grid
        low = max(0.0, origin - step / 2.0)
        high = max(hole.depth) + step / 2.0
    else:
        low = max(0.0, min(hole.depth))
        high = max(hole.depth)
    return low, high


def validate_bounds(hole: Any, target: tuple[float, float], reference: tuple[float, float]) -> None:
    for name, (top, bottom) in (("target", target), ("reference", reference)):
        features.bounds(top, bottom)
        if top < 0 or bottom < 0:
            raise ValueError(f"{name} bounds must be non-negative, got ({top}, {bottom})")
    low, high = hole_depth_range(hole)
    for name, (top, bottom) in (("target", target), ("reference", reference)):
        if top < low or bottom > high:
            raise ValueError(
                f"{name} interval [{top}, {bottom}) is outside hole depth range [{low}, {high})"
            )
        if len(features.spots(hole, top, bottom)) == 0:
            raise ValueError(
                f"{name} interval [{top}, {bottom}) contains no measured spots in hole"
            )


def result(page: dict[str, Any], claim: dict[str, Any] | None, **fields: Any) -> dict[str, Any]:
    """A worker result in the shared contract; stable request_id per continuation."""
    req_id = (
        f"r1-cont-{claim['continuation_id']}"
        if claim is not None and "continuation_id" in claim
        else f"r1-{page['number']}-{page['id'][:8]}"
    )
    return {
        "contract_version": 1,
        "request_id": req_id,
        "page_id": page["id"],
        "expected_revision": page["revision"],
        "claim": claim,
        "outcome": "complete",
        "errors": [],
        "worker": WORKER,
        **fields,
    }


def limits_evidence(page: dict[str, Any] | None = None) -> dict[str, Any]:
    assessment = page.get("assessment") if page is not None else None
    if assessment is not None:
        origin = assessment.get("origin")
        if origin == "model":
            advice_note = (
                "The advice shown comes from an experimental local model that predicts 'clarify' "
                "for nearly every case; its next-action labels were teaching rules, "
                "not expert judgement."
            )
        elif origin == "fixture":
            advice_note = (
                "Advice shown comes from a labelled fixture; no trained model was consulted."
            )
        else:
            advice_note = f"Advice shown comes from {origin}."
    else:
        advice_note = "No model advice was requested for this step."

    value = f"{SCIENTIFIC_LIMITS} {advice_note}"
    return {
        "id": "limits",
        "label": "Limits of this case",
        "value": value[:1000],
        "source": "R1 handoff; see developer/docs/training.md",
        "kind": "limitation",
        "origin": "actual",
        "state": "complete",
    }


def finish_first(store: Any, instruction: str = "") -> dict[str, Any]:
    """Record advice on the first page, then finish it so a human can review it."""
    page = working(store.snapshot())
    page = working(store.request_assessment(page["id"], page["revision"], instruction=instruction))
    advice = page["assessment"]
    numbers = {e["id"]: e["value"] for e in page["evidence"]}
    done = store.submit_result(
        result(
            page,
            None,
            summary=f"Coverage and quality calculated from the package. {numbers['qa']}"[:1000],
            evidence=[limits_evidence(page)],
            action={"type": "qa_check", "assessment_id": advice["id"]},
        )
    )
    shown = next(p for p in done["pages"] if p["id"] == page["id"])
    return {
        "page": shown["id"],
        "status": shown["status"],
        "outcome": shown["outcome"],
        "source": done["source"],
        "assessment_origin": advice["origin"],
        "model_version": advice["model_version"],
        "top_suggestion": advice["suggestions"][0]["candidate_id"],
        "evidence_ids": [e["id"] for e in shown["evidence"]],
    }


def start_case(
    store: BookStore,
    package: Path,
    package_id: str,
    target: tuple[float, float],
    reference: tuple[float, float],
    instruction: str = "",
) -> dict[str, Any]:
    """Attach scene, measure inventory and qa, request advice via store's provider, and finish
    first page.
    """
    page = working(store.snapshot())
    page = working(
        store.attach_scene(page["id"], page["revision"], package, package_id, target, reference)
    )
    for stage in ("inventory", "qa"):
        if stage not in {e["id"] for e in page["evidence"]}:
            page = working(store.measure(page["id"], page["revision"], stage))
    return finish_first(store, instruction)


def create_initial_page(
    package_id: str,
    target: tuple[float, float] | list[float],
    reference: tuple[float, float] | list[float],
) -> dict[str, Any]:
    """Create the initial page dictionary for a fresh case."""
    hole = name_of(package_id)
    t, r = target, reference
    return live_start(
        run_id=f"real-{hole}".lower(),
        title=f"Real HyLogger hole {hole}",
        question=(
            f"Does the dominant SWIR mineral group change between {r[0]:g}-{r[1]:g} m "
            f"and {t[0]:g}-{t[1]:g} m in hole {hole}?"
        ),
        summary=(
            f"Real organiser HyLogger package {package_id} from the NVCL WA catalogue "
            f"(CC BY 4.0), read with pytsg. {LIMITS}"
        ),
        progress="Checking coverage and quality of the two intervals",
    )


def continue_case(
    store: Any,
    target: tuple[float, float] | list[float] | None = None,
    reference: tuple[float, float] | list[float] | None = None,
    on_no_pending: str = "raise_exit",
) -> dict[str, Any]:
    """After a human decision: claim, acknowledge, and continue according to choice.

    - accept: run the planned comparison.
    - reject: no calculation; finish with complete outcome stating expert stopped.
    - modify with bounds: validate bounds against depth range; calculate comparison.
    - modify without bounds: no calculation; finish stating clarification is needed.
    - any other choice: refuse with clear error and zero state change.
    """
    # 1. Check pending continuation before claiming; refuse invalid inputs with no state change
    snapshot = store.snapshot()
    pending = [c for c in snapshot.get("continuations", []) if c.get("state") == "pending"]
    if not pending:
        store.expire_deliveries()
        snapshot = store.snapshot()
        pending = [c for c in snapshot.get("continuations", []) if c.get("state") == "pending"]

    if not pending:
        if on_no_pending == "raise_error":
            raise ValueError("No human decision is waiting for a worker.")
        sys.exit("No human decision is waiting for a worker.")

    step = pending[0]
    expected_continuation_id = step["id"]
    parent_page = next((p for p in snapshot["pages"] if p["id"] == step["page_id"]), None)
    if parent_page is None or "decision" not in parent_page or parent_page["decision"] is None:
        if on_no_pending == "raise_error":
            raise ValueError("No human decision is waiting for a worker.")
        sys.exit("No human decision is waiting for a worker.")

    expected_decision = parent_page["decision"]
    expected_decision_id = expected_decision.get("id")
    expected_choice = expected_decision.get("choice")

    # Guard against unknown choice with zero state change
    if expected_choice not in ("accept", "modify", "reject"):
        raise ValueError(f"Refusing unrecognised human choice: {expected_choice!r}")

    # For modify: validate bounds if provided, or require both if one is provided
    target_pair: tuple[float, float] | None = None
    reference_pair: tuple[float, float] | None = None
    if expected_choice == "modify":
        if (target is not None) != (reference is not None):
            raise ValueError("Both --target and --reference bounds must be provided together.")
        if target is not None and reference is not None:
            target_pair = (float(target[0]), float(target[1]))
            reference_pair = (float(reference[0]), float(reference[1]))
            scene = scene_of(store.path, step["page_id"])
            hole = store.science(scene["folder"], scene["package_id"])
            validate_bounds(hole, target_pair, reference_pair)

    # 2. Claim delivery
    handoff = store.claim_delivery(WORKER["name"])
    if handoff is None:
        if on_no_pending == "raise_error":
            raise ValueError("No human decision is waiting for a worker.")
        sys.exit("No human decision is waiting for a worker.")

    # F2: verify handoff matches pre-checked continuation and decision
    if (
        handoff.get("continuation_id") != expected_continuation_id
        or handoff.get("decision_id") != expected_decision_id
        or handoff.get("choice") != expected_choice
    ):
        mismatch_error = {
            "error": (
                f"Delivery mismatch: expected continuation {expected_continuation_id} "
                f"and decision {expected_decision_id}, claimed {handoff.get('continuation_id')} "
                f"and decision {handoff.get('decision_id')}"
            ),
            "code": "delivery_failed",
            "retryable": True,
        }
        store.fail_delivery(handoff["continuation_id"], handoff["attempt"], mismatch_error)
        raise ValueError(mismatch_error["error"])

    # R2: any exception after claim -> fail_delivery (retryable) so lease is not stuck
    try:
        store.acknowledge_delivery(handoff["continuation_id"], handoff["attempt"])
        claim = {"continuation_id": handoff["continuation_id"], "attempt": handoff["attempt"]}

        # Select successor by handoff["successor_id"] and scene lineage from handoff["page_id"]
        snapshot = store.snapshot()
        page = next(p for p in snapshot["pages"] if p["id"] == handoff["successor_id"])
        choice = handoff["choice"]

        # 3. Act based on choice
        if choice == "accept":
            scene = scene_of(store.path, handoff["page_id"])
            page = working(
                store.attach_scene(
                    page["id"],
                    page["revision"],
                    Path(scene["folder"]),
                    scene["package_id"],
                    tuple(scene["target"]),
                    tuple(scene["reference"]),
                    claim=claim,
                )
            )
            # R2: skip stages already on the successor
            existing_evidence_ids = {e["id"] for e in page["evidence"]}
            for stage in STAGES:
                if stage not in existing_evidence_ids:
                    page = working(store.measure(page["id"], page["revision"], stage, claim))
            numbers = {e["id"]: e["value"] for e in page["evidence"]}
            fresh_evidence = []
            if "limits" not in {e["id"] for e in page["evidence"]}:
                fresh_evidence.append(limits_evidence(page))
            done = store.submit_result(
                result(
                    page,
                    claim,
                    summary=(
                        f"Interval comparison calculated from the package. {numbers['compare']}"
                    )[:1000],
                    evidence=fresh_evidence,
                    action={"type": "interval_compare", "assessment_id": None},
                )
            )
            shown = next(p for p in done["pages"] if p["id"] == page["id"])
            return {"page": shown["id"], "status": shown["status"], "compare": numbers["compare"]}

        elif choice == "reject":
            note = handoff.get("note", "").strip()
            explanation = f"Expert stopped: {note}" if note else "Expert stopped the workflow."
            stop_evidence = {
                "id": "expert_stop",
                "label": "Expert stop",
                "value": f"{explanation}. No calculations were performed."[:1000],
                "source": "Expert workflow instruction",
                "kind": "observation",
                "origin": "actual",
                "state": "complete",
            }
            existing_evidence_ids = {e["id"] for e in page["evidence"]}
            fresh_evidence = []
            if "expert_stop" not in existing_evidence_ids:
                fresh_evidence.append(stop_evidence)
            if "limits" not in existing_evidence_ids:
                fresh_evidence.append(limits_evidence(page))
            done = store.submit_result(
                result(
                    page,
                    claim,
                    summary=f"{explanation} Nothing was calculated."[:1000],
                    evidence=fresh_evidence,
                    action={"type": "stop", "assessment_id": None},
                )
            )
            shown = next(p for p in done["pages"] if p["id"] == page["id"])
            return {"page": shown["id"], "status": shown["status"], "stopped": True}

        elif choice == "modify":
            if target_pair is not None and reference_pair is not None:
                scene = scene_of(store.path, handoff["page_id"])
                page = working(
                    store.attach_scene(
                        page["id"],
                        page["revision"],
                        Path(scene["folder"]),
                        scene["package_id"],
                        target_pair,
                        reference_pair,
                        claim=claim,
                    )
                )
                existing_evidence_ids = {e["id"] for e in page["evidence"]}
                for stage in STAGES:
                    if stage not in existing_evidence_ids:
                        page = working(store.measure(page["id"], page["revision"], stage, claim))
                numbers = {e["id"]: e["value"] for e in page["evidence"]}
                note = handoff.get("note", "").strip()
                note_desc = f"; original review note: '{note}'" if note else ""
                operator_evidence = {
                    "id": "operator_bounds",
                    "label": "Operator-supplied bounds",
                    "value": (
                        f"Target {target_pair[0]:g}–{target_pair[1]:g} m against "
                        f"reference {reference_pair[0]:g}–{reference_pair[1]:g} m "
                        f"operator-supplied{note_desc}."
                    )[:1000],
                    "source": "Operator-supplied bounds; expert confirmation is not asserted",
                    "kind": "observation",
                    "origin": "actual",
                    "state": "complete",
                }
                existing_evidence_ids = {e["id"] for e in page["evidence"]}
                fresh_evidence = []
                if "operator_bounds" not in existing_evidence_ids:
                    fresh_evidence.append(operator_evidence)
                if "limits" not in existing_evidence_ids:
                    fresh_evidence.append(limits_evidence(page))
                done = store.submit_result(
                    result(
                        page,
                        claim,
                        summary=(
                            f"Interval comparison calculated with operator-supplied bounds "
                            f"target {target_pair[0]:g}–{target_pair[1]:g} m, "
                            f"reference {reference_pair[0]:g}–{reference_pair[1]:g} m{note_desc}. "
                            f"{numbers['compare']}"
                        )[:1000],
                        evidence=fresh_evidence,
                        action={"type": "interval_compare", "assessment_id": None},
                    )
                )
                shown = next(p for p in done["pages"] if p["id"] == page["id"])
                return {
                    "page": shown["id"],
                    "status": shown["status"],
                    "compare": numbers["compare"],
                }
            else:
                note = handoff.get("note", "").strip()
                note_desc = f": '{note}'" if note else "."
                clarify_evidence = {
                    "id": "clarify_needed",
                    "label": "Clarification needed",
                    "value": (
                        f"Expert requested interval modification{note_desc} "
                        "Explicit target and reference bounds must be supplied "
                        "by operator to calculate comparison."
                    )[:1000],
                    "source": "Operator input required",
                    "kind": "observation",
                    "origin": "actual",
                    "state": "complete",
                }
                existing_evidence_ids = {e["id"] for e in page["evidence"]}
                fresh_evidence = []
                if "clarify_needed" not in existing_evidence_ids:
                    fresh_evidence.append(clarify_evidence)
                if "limits" not in existing_evidence_ids:
                    fresh_evidence.append(limits_evidence(page))
                done = store.submit_result(
                    result(
                        page,
                        claim,
                        summary=(
                            f"Clarification needed for interval modification{note_desc} "
                            "No calculation performed; "
                            "specify target and reference bounds to continue."
                        )[:1000],
                        evidence=fresh_evidence,
                        action={"type": "clarify", "assessment_id": None},
                    )
                )
                shown = next(p for p in done["pages"] if p["id"] == page["id"])
                return {
                    "page": shown["id"],
                    "status": shown["status"],
                    "clarification_needed": True,
                }

        raise ValueError(f"Refusing unrecognised human choice: {choice!r}")

    except Exception as exc:
        worker_error = {
            "error": f"Worker attempt failed: {exc}",
            "code": "worker_failed",
            "retryable": True,
        }
        store.fail_delivery(handoff["continuation_id"], handoff["attempt"], worker_error)
        raise
