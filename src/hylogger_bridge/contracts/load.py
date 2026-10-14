# Purpose: locate and parse the canonical versioned contract schema.
import json
from functools import cache
from pathlib import Path
from typing import Any

VERSION = 1


def _paths() -> list[Path]:
    here = Path(__file__).resolve().parent
    # A wheel ships the schema beside this module; a checkout keeps it at the repository root.
    return [here / f"v{VERSION}.json", here.parents[2] / "schemas" / f"v{VERSION}.json"]


@cache
def schema() -> dict[str, Any]:
    for path in _paths():
        if path.is_file():
            value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return value
    raise FileNotFoundError(f"contract schema v{VERSION} not found")
