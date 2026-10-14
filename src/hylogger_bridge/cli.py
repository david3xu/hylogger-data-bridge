# Purpose: expose local training and action recommendations through JSON files or stdin.
import argparse
import json
import sys
from pathlib import Path

from hylogger_bridge.policy import Policy
from hylogger_bridge.state import State


def main() -> int:
    parser = argparse.ArgumentParser(description="Local workflow selector (synthetic prototype)")
    commands = parser.add_subparsers(dest="command", required=True)
    training = commands.add_parser("train")
    training.add_argument("--data", type=Path, required=True)
    training.add_argument("--out", type=Path, required=True)
    recommend = commands.add_parser("recommend")
    recommend.add_argument("--model", type=Path, required=True)
    recommend.add_argument("--state", required=True, help="JSON state path, or - for stdin")
    args = parser.parse_args()
    try:
        if args.command == "train":
            from hylogger_bridge.training import train

            artifact = train(args.data, args.out)
            result: dict[str, object] = {
                "model_path": str(args.out),
                "training_rows": artifact["training_rows"],
                "validation_status": artifact["validation_status"],
            }
        else:
            document = sys.stdin.read() if args.state == "-" else Path(args.state).read_text()
            state = State.from_dict(json.loads(document))
            result = Policy.load(args.model).recommend(state)
        print(json.dumps(result, allow_nan=False))
        return 0
    except (OSError, ValueError, ImportError) as error:
        # Avoid echoing arbitrary malformed input or sensitive local file contents.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps({"error": message}), file=sys.stderr)
        return 2
