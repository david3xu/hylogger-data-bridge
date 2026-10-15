# Purpose: prepare, serve and continue one real-data case; the commands the demonstration documents.
import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hylogger_bridge.cases.runtime import (
    LIMITS as LIMITS,
)
from hylogger_bridge.cases.runtime import (
    SCIENTIFIC_LIMITS as SCIENTIFIC_LIMITS,
)
from hylogger_bridge.cases.runtime import (
    WORKER as WORKER,
)
from hylogger_bridge.cases.runtime import (
    continue_case as continue_case,
)
from hylogger_bridge.cases.runtime import (
    finish_first as finish_first,
)
from hylogger_bridge.cases.runtime import (
    hole_depth_range as hole_depth_range,
)
from hylogger_bridge.cases.runtime import (
    limits_evidence as limits_evidence,
)
from hylogger_bridge.cases.runtime import (
    result as result,
)
from hylogger_bridge.cases.runtime import (
    scene_of as scene_of,
)
from hylogger_bridge.cases.runtime import (
    validate_bounds as validate_bounds,
)
from hylogger_bridge.cases.runtime import (
    working as working,
)

__all__ = [
    "LIMITS",
    "SCIENTIFIC_LIMITS",
    "WORKER",
    "continue_case",
    "finish_first",
    "hole_depth_range",
    "limits_evidence",
    "result",
    "scene_of",
    "validate_bounds",
    "working",
]


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
