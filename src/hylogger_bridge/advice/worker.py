# Purpose: load one offline model and answer framed prediction requests without framework stdout.
import argparse
import json
import os
import socket
import sys
from pathlib import Path

from hylogger_bridge.mcp.server import claim_stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    sink = claim_stdout()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    def offline(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network connections are disabled for local model inference")

    socket.socket.connect = offline  # type: ignore[method-assign]
    socket.socket.connect_ex = offline  # type: ignore[method-assign,assignment]
    from hylogger_bridge.advice.local import LocalProvider

    provider = LocalProvider(args.model)
    sink.write(json.dumps({"ready": True, "version": provider.version}) + "\n")
    sink.flush()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            answers = provider.predict(request["state"], request["questions"])
            reply = {"id": request["id"], "answers": answers}
        except (ValueError, KeyError, RuntimeError, TypeError) as error:
            reply = {"error": str(error)}
        sink.write(json.dumps(reply, allow_nan=False) + "\n")
        sink.flush()


if __name__ == "__main__":
    main()
