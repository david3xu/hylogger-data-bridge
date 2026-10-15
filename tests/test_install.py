# Purpose: verify per-user product setup and cached launch without a source checkout dependency.
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hylogger_bridge.install import host
from hylogger_bridge.install.paths import config_path, data_home, save_config
from hylogger_bridge.install.setup import setup


def isolate(tmp_path: Path, monkeypatch: Any) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    data = tmp_path / "expert's holes"
    data.mkdir()
    return data


def test_setup_preserves_books_and_uses_installed_runtime(tmp_path: Path, monkeypatch: Any) -> None:
    folder = isolate(tmp_path, monkeypatch)
    books = tmp_path / "existing books"
    books.mkdir()
    sentinel = books / "review.sqlite3"
    sentinel.write_bytes(b"untouched")
    save_config({"cases": str(books), "existing_preference": "keep"})
    result = setup(folder, install_host=False)
    config = json.loads(config_path().read_text())
    assert result["host_installed"] is False
    assert config["runtime_python"] == sys.executable
    assert config["cases"] == str(books) and config["existing_preference"] == "keep"
    assert sentinel.read_bytes() == b"untouched"
    assert config_path().stat().st_mode & 0o777 == 0o600
    installed = Path(result["plugin"])
    assert (installed / "skills/hylogger-review/SKILL.md").is_file()
    assert "repo" not in config
    marketplace = json.loads((data_home() / ".agents/plugins/marketplace.json").read_text())
    assert marketplace["plugins"][0]["source"]["path"].startswith("./plugins/")
    setup(folder, install_host=False)
    assert sentinel.read_bytes() == b"untouched"
    # Explicit fixture mode only: ordinary installs never silently substitute fixture advice.
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "HYLOGGER_HOME"}}
    env["HYLOGGER_FIXTURE"] = "1"
    env["PATH"] = "/usr/bin:/bin"
    launch = json.loads((installed / "mcp.json").read_text())["mcpServers"]["hylogger"]
    assert launch["command"] == sys.executable
    assert launch["args"] == ["-m", "hylogger_bridge.install.cli", "mcp"]
    assert (
        json.loads((installed / ".mcp.json").read_text())["mcpServers"]["hylogger"]["command"]
        == sys.executable
    )
    done = subprocess.run(
        [launch["command"], *launch["args"]],
        input='{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n',
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    names = [t["name"] for t in json.loads(done.stdout)["result"]["tools"]]
    assert "start_case" in names and "claim_delivery" not in names


def test_missing_data_does_not_configure_host(tmp_path: Path, monkeypatch: Any) -> None:
    isolate(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="data folder"):
        setup(tmp_path / "missing")
    assert not config_path().exists()


def test_normal_setup_uses_host_workspace_without_a_fixed_folder(
    tmp_path: Path, monkeypatch: Any
) -> None:
    isolate(tmp_path, monkeypatch)
    save_config({"data_root": "/old/fixed/folder", "cases": "existing books"})
    result = setup(install_host=False)
    value = json.loads(config_path().read_text())
    assert value["workspace_mode"] == "host" and "data_root" not in value
    assert value["cases"] == "existing books" and result["data_root"] is None
    # Until the host adapter is integrated, report the missing capability instead of scanning cwd.
    from hylogger_bridge.install.cli import mcp
    from hylogger_bridge.mcp import server

    monkeypatch.setattr(server, "WORKSPACE_AUTO", False, raising=False)
    with pytest.raises(ValueError, match="connected-workspace host adapter"):
        mcp([])


def test_missing_model_interpreter_preserves_prior_settings(
    tmp_path: Path, monkeypatch: Any
) -> None:
    folder = isolate(tmp_path, monkeypatch)
    save_config({"cases": "keep", "existing_preference": True})
    original = config_path().read_bytes()
    monkeypatch.setattr("hylogger_bridge.install.setup.verify", lambda p: {})
    with pytest.raises(ValueError, match="interpreter"):
        setup(folder, tmp_path / "model", tmp_path / "missing-python", False)
    assert config_path().read_bytes() == original


def test_host_registration_uses_supported_commands_with_space_paths(
    tmp_path: Path, monkeypatch: Any
) -> None:
    isolate(tmp_path, monkeypatch)
    codex_home = tmp_path / "host config"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    settings = codex_home / "config.toml"
    settings.write_text('[mcp_servers.hylogger]\ncommand = "test"\n[preferences]\nkeep = true\n')
    prepared = setup(install_host=False)
    record = tmp_path / "calls.jsonl"
    codex = tmp_path / "codex test"
    codex.write_text(
        f"#!{sys.executable}\nimport json,sys\n"
        f"with open({str(record)!r},'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')\n"
    )
    codex.chmod(0o700)
    host.register(data_home(), codex)
    calls = [json.loads(line) for line in record.read_text().splitlines()]
    assert calls[0] == [
        "plugin",
        "marketplace",
        "add",
        str(data_home()),
        "--json",
    ]
    assert calls[1] == ["plugin", "add", "hylogger@hylogger-local", "--json"]
    assert calls[2][:4] == ["mcp", "add", "hylogger", "--env"]
    assert sys.executable in calls[2]
    assert "startup_timeout_sec = 180.0" in settings.read_text()
    assert "[preferences]\nkeep = true" in settings.read_text()
    assert Path(prepared["plugin"]).is_dir()


def test_failed_host_registration_restores_prior_settings(tmp_path: Path, monkeypatch: Any) -> None:
    isolate(tmp_path, monkeypatch)
    save_config({"existing_preference": "keep", "cases": "expert books"})
    previous = config_path().read_bytes()
    monkeypatch.setattr(host, "find_codex", lambda: Path(sys.executable))

    def failed(root: Path, codex: Path) -> None:
        raise ValueError("host unavailable")

    monkeypatch.setattr(host, "register", failed)
    with pytest.raises(ValueError, match="host unavailable"):
        setup()
    assert config_path().read_bytes() == previous


def test_installer_passes_resolved_host_path_to_the_adapter(
    tmp_path: Path, monkeypatch: Any
) -> None:
    folder = isolate(tmp_path, monkeypatch)
    codex = tmp_path / "Application Resources/codex"
    monkeypatch.setattr(host, "find_codex", lambda: codex)
    monkeypatch.setattr(host, "register", lambda root, path: None)
    setup(folder)
    assert json.loads(config_path().read_text())["codex_path"] == str(codex)
    monkeypatch.setenv("HYLOGGER_CODEX", "old value")
    monkeypatch.setenv("HYLOGGER_FIXTURE", "1")
    from hylogger_bridge.install.cli import mcp

    seen = []
    monkeypatch.setattr(
        "hylogger_bridge.mcp.server.main", lambda argv: seen.append(os.environ["HYLOGGER_CODEX"])
    )
    mcp([])
    assert seen == [str(codex)]
