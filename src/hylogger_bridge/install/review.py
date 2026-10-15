# Purpose: open real-data evidence books from an explicitly chosen local workspace.
import os
import webbrowser
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.select import startup
from hylogger_bridge.cases.registry import CaseRegistry
from hylogger_bridge.install.paths import data_home, read_config


def review(
    workspace: Path,
    package: str | None,
    target: list[float] | None,
    reference: list[float] | None,
    case: str | None = None,
    browser: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    root = workspace.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Choose an existing local workspace")
    if package and case:
        raise ValueError("Choose a package or an existing case, not both")
    if package and (target is None or reference is None):
        raise ValueError("A package review requires --target and --reference")
    config = read_config()
    if config.get("codex_path"):
        os.environ["HYLOGGER_CODEX"] = config["codex_path"]
    cases = Path(config.get("cases", data_home() / "cases"))
    if package is None and case is None:
        from hylogger_bridge.advice.provider import UnavailableProvider

        registry = CaseRegistry(cases, None, UnavailableProvider(), workspace_auto=True)
        return {"workspace": str(root), **registry.find_packages_tool(workspace=root)}
    if not config.get("model") or not config.get("model_python"):
        raise ValueError("Run setup with a local model before starting a review")
    provider = startup(Path(config["model"]), python=Path(config["model_python"]))
    registry = CaseRegistry(cases, None, provider, workspace_auto=True)
    if case is not None:
        result = registry.continue_case_tool(case, target, reference, workspace=root)
        case_id = case
    else:
        assert package is not None and target is not None and reference is not None
        result = registry.start_case(
            package, target, reference, workspace=root, session_id=session_id
        )
        case_id = result["case_id"]
    result.update(registry.open_book_tool(case_id))
    result["workspace"] = str(root)
    result["continuation"] = "Explicit command required after the expert decides in the book"
    if browser:
        result["browser_opened"] = webbrowser.open(result["url"])
    return result
