# Purpose: verify isolated inference framing, identity, failure and lifetime without weights.
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from hylogger_bridge.advice.process import ProcessProvider
from hylogger_bridge.advice.select import startup
from training.smoke import records

STUB = """
import json, sys
print(json.dumps({"ready":True,"version":"test-process"}), flush=True)
for line in sys.stdin:
    packet = json.loads(line)
    if MODE == "exit":
        break
    keys = list(packet["questions"]["follow_up"]["criteria"])
    answers = {"follow_up":{"answer":keys[0],"probabilities":{
        key:1.0 if key == keys[0] else 0.0 for key in keys}}}
    print(json.dumps({"id": packet["id"] + (1 if MODE == "foreign" else 0),
                      "answers":answers}), flush=True)
"""


def provider(tmp_path: Path, mode: str = "ok") -> ProcessProvider:
    worker = tmp_path / "stub.py"
    worker.write_text(f"MODE = {json.dumps(mode)}\n" + STUB)
    manifest: dict[str, Any] = {
        "version": "test-process",
        "data_origin": "synthetic",
        "action_types": [c["action_type"] for c in records()[0]["request"]["candidates"]],
    }
    with (
        patch("hylogger_bridge.advice.process.verify", return_value=manifest),
        patch("hylogger_bridge.advice.process.command", return_value=[sys.executable, str(worker)]),
    ):
        return ProcessProvider(tmp_path, Path(sys.executable))


def test_process_answers_multiple_requests_and_closes(tmp_path: Path) -> None:
    model = provider(tmp_path)
    try:
        for _ in range(2):
            result = model.assess(records()[0]["request"], "2026-10-15T00:00:00Z")
            assert result["origin"] == "model"
            assert result["model_version"] == "test-process"
        model.action_types = frozenset()
        with pytest.raises(ValueError, match="coverage"):
            model.assess(records()[0]["request"], "2026-10-15T00:00:00Z")
    finally:
        model.close()
    assert model._process.poll() is not None


@pytest.mark.parametrize("mode,reason", [("exit", "exited"), ("foreign", "another request")])
def test_process_failure_stops_worker_without_fixture(
    tmp_path: Path, mode: str, reason: str
) -> None:
    model = provider(tmp_path, mode)
    try:
        with pytest.raises(ValueError, match=reason):
            model.assess(records()[0]["request"], "2026-10-15T00:00:00Z")
        assert model._process.poll() is not None
    finally:
        model.close()


def test_separate_interpreter_requires_explicit_model() -> None:
    with pytest.raises(SystemExit, match="requires --model"):
        startup(None, python=Path(sys.executable))
