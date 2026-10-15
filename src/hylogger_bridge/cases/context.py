# Purpose: persist the authorised workspace of a durable investigation across entry points.
import json
from pathlib import Path
from typing import Any

from hylogger_bridge.cases.identity import is_valid_case_id


def context_path(cases: Path, case_id: str) -> Path:
    if not is_valid_case_id(case_id):
        raise ValueError("Invalid case ID")
    return cases / f"{case_id}.context.json"


def save_workspace(cases: Path, case_id: str, workspace: Path) -> None:
    path = context_path(cases, case_id)
    value = {"version": 1, "case_id": case_id, "workspace": str(workspace.resolve())}
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError("Existing case belongs to a different workspace")
        return
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def workspace_of(cases: Path, case_id: str) -> Path | None:
    path = context_path(cases, case_id)
    if not path.exists():
        return None
    value: dict[str, Any] = json.loads(path.read_text())
    if value.get("version") != 1 or value.get("case_id") != case_id:
        raise ValueError("Invalid case workspace context")
    workspace = Path(value["workspace"]).resolve()
    if not workspace.is_dir():
        raise ValueError("The original case workspace is unavailable")
    return workspace
