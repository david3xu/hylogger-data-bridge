# Purpose: verify cold-start readiness checks refuse wrong, failed and timed-out model runtimes.
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hylogger_bridge.install.check import check_model


@pytest.mark.parametrize(
    "reply,valid",
    [
        ({"ready": True, "version": "test"}, True),
        ({"ready": True, "version": "foreign"}, False),
        ("noise", False),
    ],
)
def test_model_runtime_must_confirm_exact_bundle(
    tmp_path: Path, monkeypatch: Any, reply: Any, valid: bool
) -> None:
    script = tmp_path / "worker.py"
    script.write_text(f"print({json.dumps(json.dumps(reply))})\n")
    monkeypatch.setattr("hylogger_bridge.install.check.verify", lambda f: {"version": "test"})
    monkeypatch.setattr(
        "hylogger_bridge.install.check.command", lambda p, f: [sys.executable, str(script)]
    )
    if valid:
        assert check_model(tmp_path, Path(sys.executable)) == "test"
    else:
        with pytest.raises(ValueError, match="confirm"):
            check_model(tmp_path, Path(sys.executable))


def test_model_check_timeout_never_registers_host(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr("hylogger_bridge.install.check.verify", lambda f: {"version": "test"})

    def expired(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired("test worker", 180)

    monkeypatch.setattr("hylogger_bridge.install.check.subprocess.run", expired)
    with pytest.raises(ValueError, match="host registration was not attempted"):
        check_model(tmp_path, Path(sys.executable))
