# Purpose: resolve installed assets and per-user runtime locations without a checkout.
import json
import os
from pathlib import Path
from typing import Any


def config_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return root / "hylogger/runtime.json"


def data_home() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    return root / "hylogger"


def asset(name: str) -> Path:
    installed = Path(__file__).resolve().parents[1] / "assets" / name
    if installed.is_dir():
        return installed
    repo = Path(os.environ.get("HYLOGGER_HOME", Path(__file__).resolve().parents[3]))
    source = repo / {"book": "app/dist", "plugin": "plugins/hylogger"}[name]
    return source


def read_config() -> dict[str, Any]:
    path = config_path()
    value = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(value, dict):
        raise ValueError("HyLogger runtime settings must be an object")
    return value


def save_config(value: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)
