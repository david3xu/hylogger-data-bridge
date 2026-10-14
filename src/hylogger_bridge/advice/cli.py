# Purpose: read one assessment request and emit model advice using a local checkpoint.
import argparse
import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    # Framework banners belong on stderr; stdout stays one machine-readable assessment.
    with contextlib.redirect_stdout(sys.stderr):
        from hylogger_bridge.advice.local import LocalProvider

        advice = LocalProvider(args.model).assess(request, datetime.now(UTC).isoformat())
    print(json.dumps(advice, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
