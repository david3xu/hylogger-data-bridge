# Purpose: move only the HyLogger local marketplace, preserving its previous source on failure.
import json
import subprocess
from pathlib import Path


def command(root: Path, codex: Path, *arguments: str) -> str:
    result = subprocess.run(
        [str(codex), "plugin", *arguments, "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"Codex marketplace setup failed: {result.stderr.strip()[-1000:]}")
    return result.stdout


def restore_source(root: Path, codex: Path, previous: str) -> None:
    try:
        command(root, codex, "marketplace", "remove", "hylogger-local")
        command(root, codex, "marketplace", "add", previous)
        command(root, codex, "add", "hylogger@hylogger-local")
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(
            f"HyLogger marketplace rollback failed; previous local source: {previous}"
        ) from error


def replace_source(root: Path, codex: Path) -> str:
    listing = json.loads(command(root, codex, "marketplace", "list"))
    entries = [m for m in listing["marketplaces"] if m["name"] == "hylogger-local"]
    if len(entries) != 1:
        raise ValueError("Cannot identify the existing HyLogger marketplace safely")
    source = entries[0]["marketplaceSource"]
    if source.get("sourceType") != "local" or not isinstance(source.get("source"), str):
        raise ValueError("Refusing to replace a non-local HyLogger marketplace")
    previous: str = source["source"]
    if not Path(previous).is_dir():
        raise ValueError("The previous HyLogger marketplace source is unavailable for rollback")
    command(root, codex, "marketplace", "remove", "hylogger-local")
    try:
        command(root, codex, "marketplace", "add", str(root))
    except BaseException:
        # No replacement exists if add failed; restore the known local source directly.
        command(root, codex, "marketplace", "add", previous)
        command(root, codex, "add", "hylogger@hylogger-local")
        raise
    return previous
