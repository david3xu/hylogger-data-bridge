# Purpose: register the installed plugin through the host's supported marketplace commands.
import os
import shutil
import subprocess
from pathlib import Path


def find_codex() -> Path:
    found = os.environ.get("HYLOGGER_CODEX") or shutil.which("codex")
    if found is None:
        bundled = Path("/Applications/Codex.app/Contents/Resources/codex")
        if bundled.is_file():
            found = str(bundled)
    if found is None or not Path(found).is_file():
        raise ValueError(
            "Install and sign in to Codex desktop first; then run HyLogger setup again"
        )
    return Path(found).absolute()


def register(root: Path, codex: Path) -> None:
    for arguments in (
        ["plugin", "marketplace", "add", str(root), "--json"],
        ["plugin", "add", "hylogger@hylogger-local", "--json"],
    ):
        try:
            result = subprocess.run(
                [str(codex), *arguments], capture_output=True, text=True, timeout=60, check=False
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError(
                "Codex plugin registration timed out; prior settings were restored"
            ) from error
        if result.returncode:
            raise ValueError(f"Codex plugin setup failed: {result.stderr.strip()[-1000:]}")
