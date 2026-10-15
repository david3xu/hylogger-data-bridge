# Purpose: canonical case criteria and lossless, path-safe investigation identifiers.
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from hylogger_bridge.science.features import bounds


def interval(value: Any) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("intervals require two numeric bounds [top, bottom]")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        raise ValueError("interval bounds must be numbers")
    pair = (float(value[0]), float(value[1]))
    bounds(*pair)
    if pair[0] < 0:
        raise ValueError("interval bounds must be non-negative")
    return pair


def is_valid_case_id(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= 180
        and ".." not in value
        and re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", value) is not None
    )


def case_slug(
    package_id: str, target: Any, reference: Any, workspace: Path | str | None = None
) -> str:
    if not isinstance(package_id, str) or not package_id.strip():
        raise ValueError("package_id must be a non-empty string")
    criteria: list[Any] = [package_id.strip(), interval(target), interval(reference)]
    if workspace is not None:
        criteria.append(str(Path(workspace).resolve()))
    digest = hashlib.sha256(json.dumps(criteria, allow_nan=False).encode()).hexdigest()[:32]
    prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", package_id.strip()).lower()[:60]
    if prefix.startswith("-"):
        prefix = "case" + prefix
    return f"{prefix}-{digest}"


def resolve_package(data_root: Path, package_id: str) -> Path:
    if not isinstance(package_id, str) or not package_id.strip():
        raise ValueError("package_id must be a non-empty string")
    cleaned = package_id.strip()
    if ".." in cleaned or cleaned.startswith("/") or cleaned.startswith("\\"):
        raise ValueError("package_id must name a folder inside the authorised data root")
    root = data_root.resolve()
    if not root.is_dir():
        raise ValueError("authorised data root is missing or not a directory")

    # 1. Direct path from data_root (supports relative nested path e.g. 'nvcl/SWMB007s_chips')
    candidate = (root / cleaned).resolve()
    if candidate.is_relative_to(root) and candidate.is_dir():
        folder = candidate / "pkg" if (candidate / "pkg").is_dir() else candidate
        folder = folder.resolve()
        if folder.is_relative_to(root) and folder.is_dir():
            if any(not p.resolve().is_relative_to(root) for p in folder.iterdir()):
                raise ValueError("package contains a path outside the authorised data root")
            return folder

    # 2. Check for matching nested folder by name within the authorised root
    target_name = Path(cleaned).name
    matches: list[Path] = []
    try:
        for p in root.glob(f"**/{target_name}"):
            if p.is_dir() and p.resolve().is_relative_to(root):
                f = (p / "pkg" if (p / "pkg").is_dir() else p).resolve()
                if f.is_dir() and any(f.glob("*_tsg.tsg")):
                    if f not in matches:
                        matches.append(f)
    except Exception:
        pass

    if len(matches) == 1:
        folder = matches[0]
        if any(not p.resolve().is_relative_to(root) for p in folder.iterdir()):
            raise ValueError("package contains a path outside the authorised data root")
        return folder
    if len(matches) > 1:
        raise ValueError(f"multiple matching packages found for {cleaned!r}; specify relative path")

    raise ValueError("package folder is missing or outside the authorised data root")
