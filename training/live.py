# Purpose: show one real-data assessment through the book's shared feature path, in three steps.
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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


def prepare(args: argparse.Namespace) -> None:
    from hylogger_bridge.book import BookStore

    store = BookStore(args.db, provider=Relay(args.request, None))
    page = working(store.snapshot())
    target, reference = tuple(args.target), tuple(args.reference)
    page = working(
        store.attach_scene(
            page["id"],
            page["revision"],
            args.package,
            args.package_id,
            target,
            reference,
            args.question,
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


def record(args: argparse.Namespace) -> None:
    from hylogger_bridge.book import BookStore
    from hylogger_bridge.science import live, request

    store = BookStore(args.db, provider=Relay(args.request, args.advice))
    page = working(store.snapshot())
    store.request_assessment(page["id"], page["revision"], instruction=args.instruction)
    reloaded = BookStore(args.db)
    kept = working(reloaded.snapshot())
    asked = json.loads(args.request.read_text())
    scene = live_scene(args.db, kept["id"])
    hole = live.hole_of(live.default_loader, scene)
    expected = request.evidence(hole, tuple(scene["target"]), tuple(scene["reference"]), "qa")
    summary = {
        "page": kept["id"],
        "revision": kept["revision"],
        "question": kept["question"],
        "evidence_ids": [e["id"] for e in kept["evidence"]],
        "features_in_request": asked["evidence"],
        "same_as_training_builder": asked["evidence"] == expected,
        "assessment": kept["assessment"],
    }
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "assessment"}, indent=2))
    top = kept["assessment"]["suggestions"][0]
    print("top suggestion:", top["candidate_id"], "origin:", kept["assessment"]["origin"])


def live_scene(db: Path, page_id: str) -> dict[str, Any]:
    import sqlite3

    from hylogger_bridge.store import scenes

    with sqlite3.connect(db) as connection:
        scene = scenes.get(connection, page_id)
    assert scene is not None
    found: dict[str, Any] = scene
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)
    for name in ("prepare", "advise", "record"):
        step = sub.add_parser(name)
        step.add_argument("--request", type=Path, required=True)
        if name != "advise":
            step.add_argument("--db", type=Path, required=True)
            step.add_argument("--instruction", default="")
        if name == "prepare":
            step.add_argument("--package", type=Path, required=True)
            step.add_argument("--package-id", required=True)
            step.add_argument("--target", type=float, nargs=2, required=True)
            step.add_argument("--reference", type=float, nargs=2, required=True)
            step.add_argument("--question", required=True)
        if name == "advise":
            step.add_argument("--model", type=Path, required=True)
        if name in ("advise", "record"):
            step.add_argument("--advice", type=Path, required=True)
        if name == "record":
            step.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    {"prepare": prepare, "advise": advise, "record": record}[args.step](args)
    sys.exit(0)


if __name__ == "__main__":
    main()
