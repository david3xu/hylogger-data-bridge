# Purpose: prepare, serve and continue one real-data case; the commands the demonstration documents.
import argparse
import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKER = {"kind": "agent", "name": "r1-science-worker"}
SCIENTIFIC_LIMITS = (
    "No assay or assay-overlap result is used or claimed; "
    "measurements are TSG interpretations only."
)
LIMITS = SCIENTIFIC_LIMITS


class Captured(Exception):
    """Raised by the capturing provider once it has saved the request."""


class Relay:
    """Hands a request to another environment, then replays that environment's advice.

    The model runs where its libraries live; the book runs where pytsg lives. Replay only
    returns advice for the identical request, and the book still validates and fences it.
    """

    def __init__(self, request: Path, advice: Path | None) -> None:
        self.request, self.advice = request, advice

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        if self.advice is None:
            self.request.write_text(json.dumps(request, indent=2) + "\n")
            raise Captured
        if json.loads(self.request.read_text()) != request:
            raise ValueError("the book's request changed since the model saw it")
        advice: dict[str, Any] = json.loads(self.advice.read_text())
        return advice


def working(snapshot: dict[str, Any]) -> dict[str, Any]:
    page: dict[str, Any] = next(
        p for p in snapshot["pages"] if p["id"] == snapshot["current_page_id"]
    )
    return page


def scene_of(book: Path, page_id: str | None) -> dict[str, Any]:
    from hylogger_bridge.store import scenes

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
    from hylogger_bridge.science import features

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
    from hylogger_bridge.science import features

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


def prepare(args: argparse.Namespace, science: Any = None) -> None:
    from hylogger_bridge.book import BookStore
    from hylogger_bridge.pages.live import start
    from hylogger_bridge.science.package import name_of

    hole = name_of(args.package_id)
    t, r = args.target, args.reference
    first = start(
        run_id=f"real-{hole}".lower(),
        title=f"Real HyLogger hole {hole}",
        question=(
            f"Does the dominant SWIR mineral group change between {r[0]:g}-{r[1]:g} m "
            f"and {t[0]:g}-{t[1]:g} m in hole {hole}?"
        ),
        summary=(
            f"Real organiser HyLogger package {args.package_id} from the NVCL WA catalogue "
            f"(CC BY 4.0), read with pytsg. {LIMITS}"
        ),
        progress="Checking coverage and quality of the two intervals",
    )
    store = BookStore(args.book, provider=Relay(args.request, None), start=first, science=science)
    page = working(store.snapshot())
    page = working(
        store.attach_scene(
            page["id"], page["revision"], args.package, args.package_id, tuple(t), tuple(r)
        )
    )
    for stage in ("inventory", "qa"):
        page = working(store.measure(page["id"], page["revision"], stage))
    try:
        store.request_assessment(page["id"], page["revision"], instruction=args.instruction)
    except Captured:
        print("request saved:", args.request)


def advise(args: argparse.Namespace) -> None:
    import socket

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    def no_network(*unused: object, **ignored: object) -> None:
        raise RuntimeError("network access is disabled during this offline inference")

    socket.socket.connect = no_network  # type: ignore[method-assign]
    from hylogger_bridge.advice.local import LocalProvider

    provider = LocalProvider(args.model)
    request = json.loads(args.request.read_text())
    advice = provider.assess(request, datetime.now(UTC).isoformat())
    args.advice.write_text(json.dumps(advice, indent=2) + "\n")
    print("advice saved:", args.advice, advice["origin"], advice["model_version"])


def finish_first(store: Any, instruction: str) -> dict[str, Any]:
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


def record(args: argparse.Namespace) -> None:
    """Finish the first page with saved model advice, or with labelled fixture advice."""
    from hylogger_bridge.advice.provider import FixtureProvider
    from hylogger_bridge.book import BookStore

    provider: Any = FixtureProvider() if args.fixture else Relay(args.request, args.advice)
    summary = finish_first(BookStore(args.book, provider=provider), args.instruction)
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def case_files(book: Path) -> dict[str, Path]:
    """The request, advice and first-page summary files kept beside a case's book."""
    return {name: book.with_suffix(f".{name}.json") for name in ("request", "advice", "first-page")}


def model_python(args: argparse.Namespace) -> str | None:
    """The prepared model environment's interpreter, needed only when --model is given."""
    if args.model is None:
        return None
    found: str | None = args.model_python or os.environ.get("HYLOGGER_MODEL_PYTHON")
    if not found:
        sys.exit("--model needs --model-python or HYLOGGER_MODEL_PYTHON (the model environment).")
    return found


def demo(args: argparse.Namespace, science: Any = None) -> dict[str, Any]:
    """One command for a fresh real case: prepare, advise, record, then say what to run next.

    Without --model the first page carries labelled fixture advice; the QA numbers are still
    calculated from the real package. With --model the saved local model is run offline in its
    own environment. Nothing is decided here: the human decides in the browser.
    """
    python = model_python(args)
    if args.book.exists():
        sys.exit(f"{args.book} already exists; give a new --book for a fresh case.")
    files = case_files(args.book)
    args.book.parent.mkdir(parents=True, exist_ok=True)
    prepare(
        argparse.Namespace(
            book=args.book,
            request=files["request"],
            package=args.package,
            package_id=args.package_id,
            target=args.target,
            reference=args.reference,
            instruction=args.instruction,
        ),
        science=science,
    )
    if python is not None:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(p for p in ("src", ".", env.get("PYTHONPATH")) if p)
        command = [python, "-m", "training.live", "advise", "--request", str(files["request"])]
        command += ["--model", str(args.model), "--advice", str(files["advice"])]
        subprocess.run(command, check=True, env=env)
    record(
        argparse.Namespace(
            book=args.book,
            request=files["request"],
            advice=files["advice"],
            fixture=python is None,
            instruction=args.instruction,
            out=files["first-page"],
        )
    )
    summary: dict[str, Any] = json.loads(files["first-page"].read_text())
    print("\nThe first page is ready for your review.")
    print(f"  Serve the book:  uv run python -m hylogger_bridge.book_server --db {args.book}")
    print("  Open http://127.0.0.1:8766, read the evidence, choose and write a note.")
    print(f"  Then continue:   python -m training.live continue --book {args.book}")
    return summary


def continue_case(
    store: Any,
    target: tuple[float, float] | list[float] | None = None,
    reference: tuple[float, float] | list[float] | None = None,
) -> dict[str, Any]:
    """After a human decision: claim, acknowledge, and continue according to choice.

    - accept: run the planned comparison.
    - reject: no calculation; finish with complete outcome stating expert stopped.
    - modify with bounds: validate bounds against depth range; calculate comparison.
    - modify without bounds: no calculation; finish stating clarification is needed.
    - any other choice: refuse with clear error and zero state change.
    """
    from hylogger_bridge.science.request import STAGES

    # 1. Check pending continuation before claiming; refuse invalid inputs with no state change
    snapshot = store.snapshot()
    pending = [c for c in snapshot.get("continuations", []) if c.get("state") == "pending"]
    if not pending:
        store.expire_deliveries()
        snapshot = store.snapshot()
        pending = [c for c in snapshot.get("continuations", []) if c.get("state") == "pending"]

    if not pending:
        sys.exit("No human decision is waiting for a worker.")

    step = pending[0]
    expected_continuation_id = step["id"]
    parent_page = next((p for p in snapshot["pages"] if p["id"] == step["page_id"]), None)
    if parent_page is None or "decision" not in parent_page or parent_page["decision"] is None:
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
                note_desc = f" from note '{note}'" if note else ""
                operator_evidence = {
                    "id": "operator_bounds",
                    "label": "Operator-supplied bounds",
                    "value": (
                        f"Target {target_pair[0]:g}–{target_pair[1]:g} m against "
                        f"reference {reference_pair[0]:g}–{reference_pair[1]:g} m "
                        f"operator-supplied{note_desc}."
                    )[:1000],
                    "source": "Operator bounds from expert note",
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


def follow(args: argparse.Namespace) -> None:
    from hylogger_bridge.book import BookStore

    print(
        json.dumps(
            continue_case(
                BookStore(args.book),
                target=args.target,
                reference=args.reference,
            ),
            indent=2,
        )
    )


SWMB007S = Path("data/raw/nvcl/SWMB007s_chips/pkg")


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description="Prepare, review and continue one real-data case.")
    sub = top.add_subparsers(dest="step", required=True)
    for name in ("prepare", "advise", "record", "continue"):
        step = sub.add_parser(name)
        if name != "advise":
            step.add_argument("--book", type=Path, required=True)
        if name in ("prepare", "advise"):
            step.add_argument("--request", type=Path, required=True)
        if name == "record":
            step.add_argument("--request", type=Path)
        if name in ("prepare", "record"):
            step.add_argument("--instruction", default="")
        if name == "prepare":
            step.add_argument("--package", type=Path, required=True)
            step.add_argument("--package-id", required=True)
            step.add_argument("--target", type=float, nargs=2, required=True)
            step.add_argument("--reference", type=float, nargs=2, required=True)
        if name == "continue":
            step.add_argument("--target", type=float, nargs=2, default=None)
            step.add_argument("--reference", type=float, nargs=2, default=None)
        if name == "advise":
            step.add_argument("--model", type=Path, required=True)
            step.add_argument("--advice", type=Path, required=True)
        if name == "record":
            source = step.add_mutually_exclusive_group(required=True)
            source.add_argument("--advice", type=Path, help="advice saved by `advise`")
            source.add_argument(
                "--fixture", action="store_true", help="labelled fixture advice; no trained model"
            )
            step.add_argument("--out", type=Path, required=True)
    case = sub.add_parser("demo", help="prepare a fresh real case in one step")
    case.add_argument("--book", type=Path, required=True)
    case.add_argument("--package", type=Path, default=SWMB007S)
    case.add_argument("--package-id", default="SWMB007s_chips")
    case.add_argument("--target", type=float, nargs=2, default=[5.0, 10.0])
    case.add_argument("--reference", type=float, nargs=2, default=[0.0, 5.0])
    case.add_argument("--instruction", default="")
    case.add_argument("--model", type=Path, default=None, help="local model bundle (optional)")
    case.add_argument("--model-python", default=None, help="model environment interpreter")
    return top


def main() -> None:
    args = parser().parse_args()
    if args.step == "record" and args.advice is not None and args.request is None:
        sys.exit("record --advice needs --request (the request the model saw).")
    if args.step == "demo":
        demo(args)
        return
    steps: dict[str, Callable[[argparse.Namespace], None]] = {
        "prepare": prepare,
        "advise": advise,
        "record": record,
        "continue": follow,
    }
    steps[args.step](args)


if __name__ == "__main__":
    main()
