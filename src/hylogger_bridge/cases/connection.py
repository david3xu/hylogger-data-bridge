# Purpose: expose whether a case has a configured conversation return destination.
from pathlib import Path
from typing import Any

from hylogger_bridge.cases.dispatch import load_session_binding


def describe(cases: Path, case_id: str) -> dict[str, Any]:
    binding = load_session_binding(cases, case_id)
    return {
        "session_binding": binding,
        "return_mode": "automatic" if binding else "manual",
        "automatic_return": binding is not None,
        "return_message": (
            "Return destination configured; host delivery and work completion are separate states."
            if binding
            else (
                "No conversation is bound. Automatic return is unavailable; "
                "explicit chat follow-up is required."
            )
        ),
    }
