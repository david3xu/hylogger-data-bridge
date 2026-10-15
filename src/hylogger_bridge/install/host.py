# Purpose: register the installed plugin through the host's supported marketplace commands.
import json
import os
import shutil
import subprocess
from pathlib import Path

from hylogger_bridge.install import host_config
from hylogger_bridge.install.paths import config_path, data_home


def find_codex() -> Path:
    candidates = [
        os.environ.get("HYLOGGER_CODEX"),
        os.environ.get("CODEX_CLI_PATH"),
        shutil.which("codex"),
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
    ]
    for found in candidates:
        if found and Path(found).is_file() and os.access(found, os.X_OK):
            return Path(found).absolute()
    raise ValueError("Install and sign in to Codex desktop first; then run HyLogger setup again")


def register(root: Path, codex: Path) -> None:
    marketplace = json.loads((root / ".agents/plugins/marketplace.json").read_text())
    entry = next(p for p in marketplace["plugins"] if p["name"] == "hylogger")
    plugin = (root / entry["source"]["path"]).resolve()
    if not plugin.is_relative_to(root.resolve()):
        raise ValueError("Installed plugin path escapes its data directory")
    launch = json.loads((plugin / "mcp.json").read_text())["mcpServers"]["hylogger"]
    arguments_list = [
        ["plugin", "marketplace", "add", str(root), "--json"],
        ["plugin", "add", "hylogger@hylogger-local", "--json"],
        [
            "mcp",
            "add",
            "hylogger",
            "--env",
            f"XDG_CONFIG_HOME={config_path().parent.parent}",
            "--env",
            f"XDG_DATA_HOME={data_home().parent}",
            "--env",
            f"HYLOGGER_CODEX={codex}",
            "--",
            launch["command"],
            *launch["args"],
        ],
    ]
    settings = host_config.config_path()
    previous = settings.read_bytes() if settings.exists() else None
    try:
        for arguments in arguments_list:
            result = subprocess.run(
                [str(codex), *arguments], capture_output=True, text=True, timeout=60, check=False
            )
            if result.returncode:
                raise ValueError(f"Codex plugin setup failed: {result.stderr.strip()[-1000:]}")
        host_config.timeouts()
    except BaseException:
        if previous is None:
            settings.unlink(missing_ok=True)
        else:
            settings.write_bytes(previous)
        raise
