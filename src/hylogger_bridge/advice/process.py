# Purpose: consult the actual local checkpoint in its separate, persistent model environment.
import atexit
import json
import os
import select
import subprocess
import threading
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.assets import verify
from hylogger_bridge.advice.provider import ModelProvider


def command(python: Path, folder: Path) -> list[str]:
    return [str(python), "-m", "hylogger_bridge.advice.worker", "--model", str(folder)]


class ProcessProvider(ModelProvider):
    def __init__(self, folder: Path, python: Path) -> None:
        if not python.is_file() or not os.access(python, os.X_OK):
            raise ValueError("model interpreter is missing or not executable")
        manifest = verify(folder)
        self.action_types = frozenset(manifest["action_types"])
        self._lock = threading.Lock()
        self._serial = 0
        self._process = subprocess.Popen(
            command(python, folder.resolve()),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            hello = self._read(60)
            if hello.get("version") != manifest["version"] or not hello.get("ready"):
                raise ValueError("model worker did not load the requested checkpoint")
        except BaseException:
            self.close()
            raise
        atexit.register(self.close)
        super().__init__(self._predict, manifest["version"], manifest["data_origin"])

    def _read(self, timeout: float) -> dict[str, Any]:
        stream = self._process.stdout
        if stream is None or not select.select([stream], [], [], timeout)[0]:
            raise ValueError("local model worker timed out; restart the MCP service")
        line = stream.readline()
        if not line:
            raise ValueError("local model worker exited; no fixture was substituted")
        value: dict[str, Any] = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("local model worker returned an invalid packet")
        if "error" in value:
            raise ValueError(f"local model worker: {value['error']}")
        return value

    def _predict(self, state: str, questions: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._serial += 1
            stream = self._process.stdin
            if stream is None or self._process.poll() is not None:
                raise ValueError("local model worker is unavailable")
            packet = {"id": self._serial, "state": state, "questions": questions}
            try:
                stream.write(json.dumps(packet, allow_nan=False) + "\n")
                stream.flush()
                reply = self._read(60)
                if reply.get("id") != self._serial:
                    raise ValueError("local model reply belongs to another request")
            except (OSError, ValueError):
                self.close()
                raise
            answers: dict[str, Any] = reply["answers"]
            return answers

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        if not {c["action_type"] for c in request["candidates"]} <= self.action_types:
            raise ValueError("candidate actions exceed this checkpoint's declared coverage")
        return super().assess(request, at)

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3)
        for stream in (self._process.stdin, self._process.stdout):
            if stream is not None:
                stream.close()
