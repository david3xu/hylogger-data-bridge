# Purpose: execute installer shell branches without dependencies, networking or real host changes.
import hashlib
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("skip_host", [False, True])
def test_default_and_standalone_install_do_not_expand_an_empty_array(
    tmp_path: Path, skip_host: bool
) -> None:
    kit = tmp_path / "kit"
    kit.mkdir()
    source = Path(__file__).resolve().parents[1] / "packaging/Install.command"
    (kit / "Install.command").write_text(source.read_text())
    (kit / "build-id").write_text("testbuild\n")
    (kit / "model-version").write_text("fixture-model\n")
    (kit / "runtime.txt").write_text("# shell fixture only\n")
    (kit / "uv").write_text("#!/bin/sh\nexit 0\n")
    (kit / "uv").chmod(0o755)
    runtime = tmp_path / "data/hylogger/runtimes/testbuild/bin"
    runtime.mkdir(parents=True)
    (runtime / "python").write_text("fixture interpreter, never invoked")
    (runtime / "hylogger").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$RUNTIME_RECORD"\n')
    (runtime / "hylogger").chmod(0o755)
    (tmp_path / "data/hylogger/models/fixture-model").mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text(
        '#!/bin/sh\nif [ "$1" = -s ]; then echo Darwin; else echo arm64; fi\n'
    )
    (fake_bin / "uname").chmod(0o755)
    files = [p for p in kit.iterdir() if p.is_file()]
    (kit / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files)
    )
    record = tmp_path / "calls"
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "RUNTIME_RECORD": str(record),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
    }
    env.pop("HYLOGGER_MODEL_BUNDLE", None)
    if skip_host:
        env["HYLOGGER_SKIP_HOST"] = "1"
    else:
        env.pop("HYLOGGER_SKIP_HOST", None)
    result = subprocess.run(
        ["/bin/bash", str(kit / "Install.command")],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    calls = record.read_text().splitlines()
    assert len(calls) == 2 and calls[1].startswith("setup --model ")
    assert ("--no-host" in calls[1]) == skip_host
    assert "HyLogger managed launcher" in (tmp_path / "data/hylogger/hylogger").read_text()
