# Purpose: prepare, serve and continue one real-data case; the commands the demonstration documents.
import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKER = {"kind": "agent", "name": "r1-science-worker"}
LIMITS = (
    "No assay or assay-overlap result is used or claimed. The advice shown comes from an "
    "experimental local model that predicts 'clarify' for nearly every case; its next-action "
    "labels were teaching rules, not expert judgement. Real measurements, weak model."
)


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


def scene_of(book: Path, page_id: str) -> dict[str, Any]:
    from hylogger_bridge.store import scenes

    with sqlite3.connect(book) as connection:
        scene = scenes.get(connection, page_id)
    assert scene is not None
    found: dict[str, Any] = scene
    return found


def result(page: dict[str, Any], claim: dict[str, Any] | None, **fields: Any) -> dict[str, Any]:
    """A worker result in the shared contract; the first page has no delivery to claim."""
    return {
        "contract_version": 1,
        "request_id": f"r1-{page['number']}-{page['id'][:8]}",
        "page_id": page["id"],
        "expected_revision": page["revision"],
        "claim": claim,
        "outcome": "complete",
        "errors": [],
        "worker": WORKER,
        **fields,
    }


def limits_evidence() -> dict[str, Any]:
    return {
        "id": "limits",
        "label": "Limits of this case",
        "value": LIMITS,
        "source": "R1 handoff; see developer/docs/training.md",
        "kind": "limitation",
        "origin": "actual",
        "state": "complete",
    }


def prepare(args: argparse.Namespace) -> None:
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
    store = BookStore(args.book, provider=Relay(args.request, None), start=first)
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
    import os
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
            evidence=[limits_evidence()],
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
    from hylogger_bridge.book import BookStore

    summary = finish_first(
        BookStore(args.book, provider=Relay(args.request, args.advice)), args.instruction
    )
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def continue_case(store: Any) -> dict[str, Any]:
    """After a human decision: claim, acknowledge, calculate the comparison, complete."""
    from hylogger_bridge.science.request import STAGES

    handoff = store.claim_delivery(WORKER["name"])
    if handoff is None:
        sys.exit("No human decision is waiting for a worker.")
    store.acknowledge_delivery(handoff["continuation_id"], handoff["attempt"])
    claim = {"continuation_id": handoff["continuation_id"], "attempt": handoff["attempt"]}
    page = working(store.snapshot())
    scene = scene_of(store.path, page["parent_id"])
    page = working(
        store.attach_scene(
            page["id"],
            page["revision"],
            Path(scene["folder"]),
            scene["package_id"],
            tuple(scene["target"]),
            tuple(scene["reference"]),
        )
    )
    for stage in STAGES:
        page = working(store.measure(page["id"], page["revision"], stage, claim))
    numbers = {e["id"]: e["value"] for e in page["evidence"]}
    done = store.submit_result(
        result(
            page,
            claim,
            summary=f"Interval comparison calculated from the package. {numbers['compare']}"[:1000],
            evidence=[limits_evidence()],
            action={"type": "interval_compare", "assessment_id": None},
        )
    )
    shown = next(p for p in done["pages"] if p["id"] == page["id"])
    return {"page": shown["id"], "status": shown["status"], "compare": numbers["compare"]}


def follow(args: argparse.Namespace) -> None:
    from hylogger_bridge.book import BookStore

    print(json.dumps(continue_case(BookStore(args.book)), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)
    for name in ("prepare", "advise", "record", "continue"):
        step = sub.add_parser(name)
        if name != "advise":
            step.add_argument("--book", type=Path, required=True)
        if name != "continue":
            step.add_argument("--request", type=Path, required=True)
        if name in ("prepare", "record"):
            step.add_argument("--instruction", default="")
        if name == "prepare":
            step.add_argument("--package", type=Path, required=True)
            step.add_argument("--package-id", required=True)
            step.add_argument("--target", type=float, nargs=2, required=True)
            step.add_argument("--reference", type=float, nargs=2, required=True)
        if name == "advise":
            step.add_argument("--model", type=Path, required=True)
        if name in ("advise", "record"):
            step.add_argument("--advice", type=Path, required=True)
        if name == "record":
            step.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    {"prepare": prepare, "advise": advise, "record": record, "continue": follow}[args.step](args)


if __name__ == "__main__":
    main()
