# Purpose: expose the same durable expert case operations to installed command-line clients.
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.select import startup
from hylogger_bridge.cases.registry import CaseRegistry
from hylogger_bridge.install.paths import read_config


def case_operation(
    operation: str,
    case_id: str,
    continuation: str | None = None,
    decision: str | None = None,
    unbind: bool = False,
    target: list[float] | None = None,
    reference: list[float] | None = None,
) -> dict[str, Any]:
    config = read_config()
    if not config.get("cases"):
        raise ValueError("Run HyLogger setup first")
    if operation == "read" or operation == "open":
        from hylogger_bridge.advice.provider import UnavailableProvider

        provider: Any = UnavailableProvider()
    else:
        if not config.get("model") or not config.get("model_python"):
            raise ValueError("No local model is configured")
        provider = startup(Path(config["model"]), python=Path(config["model_python"]))
    registry = CaseRegistry(Path(config["cases"]), None, provider, workspace_auto=True)
    try:
        if operation == "read":
            return registry.read_case(case_id, unbind=unbind)
        if operation == "open":
            return registry.open_book_tool(case_id)
        return registry.continue_case_tool(
            case_id,
            target,
            reference,
            continuation_id=continuation,
            decision_id=decision,
            unbind=unbind,
        )
    finally:
        registry.close()
