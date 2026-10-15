# Purpose: calculate a scientific page's features from its attached scene; callers never supply them.
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hylogger_bridge.science import features, package, request
from hylogger_bridge.science.hole import Hole

Loader = Callable[[str, str], Hole]


def default_loader(folder: str, package_id: str) -> Hole:
    return package.read(Path(folder), package_id)


def _pair(value: Any) -> tuple[float, float]:
    top, bottom = value
    features.bounds(float(top), float(bottom))
    return float(top), float(bottom)


def attach(
    load: Loader, folder: str, package_id: str, target: Any, reference: Any
) -> dict[str, Any]:
    """Read the package once, check its identity and the intervals, and record what was read."""
    hole = load(folder, package_id)
    return {
        "folder": folder,
        "package_id": package_id,
        "hole_id": hole.hole_id,
        "target": list(_pair(target)),
        "reference": list(_pair(reference)),
        "method": features.METHOD,
        "files": [list(item) for item in hole.files],
        "identity": [list(item) for item in hole.identity],
    }


def hole_of(load: Loader, scene: dict[str, Any]) -> Hole:
    hole = load(scene["folder"], scene["package_id"])
    if [list(item) for item in hole.files] != scene["files"]:
        raise ValueError("the package files changed since this page was attached to them")
    if scene["method"] != features.METHOD:
        raise ValueError("this page's features were defined by a different method version")
    return hole


def known(load: Loader, scene: dict[str, Any]) -> dict[str, features.Features]:
    """Every feature of the scene, by evidence ID; the page decides which are observed so far."""
    hole = hole_of(load, scene)
    return request.measured(hole, _pair(scene["target"]), _pair(scene["reference"]))


def candidates(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return request.candidates(_pair(scene["target"]), _pair(scene["reference"]))


def evidence_text(stage: str, values: features.Features) -> str:
    shown = ", ".join(f"{key}={value}" for key, value in values.items())
    return f"{stage}: {shown}"[:4000]
