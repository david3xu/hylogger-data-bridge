# Purpose: require an explicit return destination or manual mode before an expert case starts.
from typing import Any

from hylogger_bridge.cases.dispatch import is_valid_session_id
from hylogger_bridge.cases.registry import CaseRegistry


def execute(registry: CaseRegistry, arguments: dict[str, Any]) -> dict[str, Any]:
    session = arguments.get("session_id")
    manual = arguments.get("manual_return", False)
    if not isinstance(manual, bool):
        raise ValueError("manual_return must be a boolean")
    if manual and session is not None:
        raise ValueError("Choose session_id for automatic return OR manual_return=true")
    if not manual and (not isinstance(session, str) or not is_valid_session_id(session)):
        raise ValueError(
            "Automatic return requires the current conversation's verified session_id. "
            "Before retrying start_case, use the calling conversation's shell tool to read "
            "CODEX_THREAD_ID (or CODEX_SESSION_ID), then pass that UUID as session_id. "
            "Do not use the shared MCP server's environment or guess an ID. "
            "If a verified ID is unavailable, explain that automatic return is unavailable "
            "and pass manual_return=true only for explicit manual follow-up. "
            "No case has been created by this request."
        )
    return registry.start_case(
        arguments["package_id"],
        arguments["target"],
        arguments["reference"],
        session_id=session,
        workspace=arguments.get("workspace"),
    )
