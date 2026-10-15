# Purpose: set only HyLogger MCP timeouts while preserving all other host configuration.
import os
import re
import tomllib
from pathlib import Path


def config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"


def timeouts() -> None:
    path = config_path()
    text = path.read_text()
    pattern = r"(?ms)^\[mcp_servers\.hylogger\]\s*\n(.*?)(?=^\[|\Z)"
    match = re.search(pattern, text)
    if match is None:
        raise ValueError("Codex did not create the HyLogger MCP configuration")
    body = re.sub(r"(?m)^(?:startup_timeout_sec|tool_timeout_sec)\s*=.*\n?", "", match[1])
    body = "startup_timeout_sec = 180.0\ntool_timeout_sec = 240.0\n" + body
    updated = text[: match.start(1)] + body + text[match.end(1) :]
    tomllib.loads(updated)
    temporary = path.with_suffix(".hylogger.tmp")
    temporary.write_text(updated)
    temporary.chmod(0o600)
    temporary.replace(path)
