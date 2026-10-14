# Purpose: reload a verified base/adapter decision model offline and compare advisory predictions.
import argparse
import json
import os
import socket
import time
from pathlib import Path

from hylogger_bridge.advice.assets import verify
from hylogger_bridge.advice.encode import encode


def check(folder: Path, output: Path, tolerance: float) -> None:
    manifest = verify(folder)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    def no_network(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network access is disabled during the offline reload check")

    socket.socket.connect = no_network  # type: ignore[method-assign]
    socket.socket.connect_ex = no_network  # type: ignore[method-assign, assignment]
    from hylogger_bridge.advice.local import LocalProvider

    start = time.monotonic()
    provider = LocalProvider(folder)
    predict = provider.predict
    checks = []
    for ref in manifest["reference"]:
        state, questions, _ = encode(ref["request"])
        answers = predict(state, questions)
        expected = ref["answers"]["follow_up"]
        actual = answers["follow_up"]
        gap = max(
            abs(actual["probabilities"][key] - value)
            for key, value in expected["probabilities"].items()
        )
        if expected["answer"] != actual["answer"] or gap > tolerance:
            raise ValueError(f"export inference differs: maximum probability difference {gap}")
        from datetime import UTC, datetime

        advice = provider.assess(ref["request"], datetime.now(UTC).isoformat())
        checks.append({"maximum_probability_difference": gap, "assessment": advice})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "offline_requested": True,
                "checks": checks,
                "elapsed_seconds": time.monotonic() - start,
                "tolerance": tolerance,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Offline reload and {len(checks)} assessment comparisons passed: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/model/local.json"))
    parser.add_argument("--tolerance", type=float, default=0.03)
    args = parser.parse_args()
    if not 0 <= args.tolerance <= 0.1:
        parser.error("tolerance must be between zero and 0.1")
    check(args.folder, args.output, args.tolerance)


if __name__ == "__main__":
    main()
