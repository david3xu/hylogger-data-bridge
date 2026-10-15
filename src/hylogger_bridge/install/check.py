# Purpose: validate an installed checkpoint runtime before registering it with a chat host.
import json
import subprocess
from pathlib import Path

from hylogger_bridge.advice.assets import verify
from hylogger_bridge.advice.process import command


def check_model(folder: Path, python: Path, timeout: float = 180) -> str:
    manifest = verify(folder)
    try:
        result = subprocess.run(
            command(python, folder.resolve()),
            input="",
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(
            "local model startup timed out; host registration was not attempted"
        ) from error
    if result.returncode:
        raise ValueError(f"local model could not start: {result.stderr.strip()[-1000:]}")
    try:
        packet = json.loads(result.stdout)
        matches = packet.get("ready") is True and packet.get("version") == manifest["version"]
    except (ValueError, AttributeError):
        matches = False
    if not matches:
        raise ValueError("model runtime did not confirm the requested checkpoint version")
    return str(manifest["version"])
