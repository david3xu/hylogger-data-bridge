# Purpose: prevent the expert MCP surface from silently creating disconnected automatic cases.
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_science import chips

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.cases.registry import CaseRegistry
from hylogger_bridge.mcp.server import handle

SESSION = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"


def prepare(tmp_path: Path) -> tuple[CaseRegistry, dict[str, Any], list[Any]]:
    workspace = tmp_path / "workspace"
    package = workspace / "FIX001_chips/pkg"
    package.mkdir(parents=True)
    (package / "FIX001_tsg.tsg").write_text("labelled fixture")
    sent: list[Any] = []

    def runner(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        sent.append(args[0])
        return subprocess.CompletedProcess(args[0], 0, "Queued message fixture", "")

    reg = CaseRegistry(
        tmp_path / "cases",
        None,
        FixtureProvider(),
        science=lambda *a: chips(),
        workspace_auto=True,
        cmd_runner=runner,
        server_launcher=lambda *a: "http://127.0.0.1:12345",
    )
    return (
        reg,
        {
            "package_id": "FIX001_chips",
            "target": [5, 10],
            "reference": [0, 5],
            "workspace": str(workspace),
        },
        sent,
    )


def ask(reg: CaseRegistry, name: str, args: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    result = handle(
        reg,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
        tools_mode="expert",
    )
    assert result is not None
    body = result["result"]
    return body["isError"], json.loads(body["content"][0]["text"])


@pytest.mark.parametrize("session", [None, "", "invalid"])
def test_missing_or_invalid_conversation_refused_before_science_or_book(
    tmp_path: Path,
    monkeypatch: Any,
    session: str | None,
) -> None:
    reg, args, sent = prepare(tmp_path)
    monkeypatch.setenv("CODEX_THREAD_ID", OTHER)
    monkeypatch.setenv("CODEX_SESSION_ID", OTHER)
    # Shared process environment must never become a destination for another calling chat.
    reg.science = lambda *a: pytest.fail("unbound request reached science")
    failed, error = ask(reg, "start_case", {**args, "session_id": session})
    assert failed and "verified session_id" in error["error"]
    assert "CODEX_THREAD_ID" in error["error"]
    assert not list(reg.cases_dir.glob("*.sqlite3")) and not sent


def test_explicit_manual_case_and_open_book_report_no_automatic_return(tmp_path: Path) -> None:
    reg, args, sent = prepare(tmp_path)
    failed, result = ask(reg, "start_case", {**args, "manual_return": True})
    assert not failed
    assert result["session_binding"] is None and not result["automatic_return"]
    failed, opened = ask(reg, "open_book", {"case_id": result["case_id"]})
    assert not failed and opened["return_mode"] == "manual"
    assert "explicit chat follow-up" in opened["return_message"] and not sent
    assert opened["notification_visibility"] == "none"
    assert opened["note_delivery"] == "read_from_saved_decision"
    before = reg.get_store(result["case_id"]).snapshot()
    failed, repeated = ask(reg, "open_book", {"case_id": result["case_id"]})
    assert not failed and repeated["url"] == opened["url"]
    assert repeated["browser_policy"] == "reuse_existing_tab"
    assert reg.get_store(result["case_id"]).snapshot() == before
    reg.close()


def test_binding_repair_preserves_history_and_notifies_only_verified_conversation(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    reg, args, sent = prepare(tmp_path)
    monkeypatch.setenv("CODEX_THREAD_ID", OTHER)
    _, result = ask(reg, "start_case", {**args, "manual_return": True})
    case = result["case_id"]
    store = reg.get_store(case)
    page = store.snapshot()["pages"][0]
    before = store.decide(page["id"], page["revision"], "modify", "explain first", "test")
    failed, repaired = ask(reg, "start_case", {**args, "session_id": SESSION})
    assert not failed and repaired["reused"] and repaired["automatic_return"]
    assert repaired["session_binding"]["session_id"] == SESSION
    reg.bind_case(case, SESSION)  # forces one observed check, serialized with the watcher
    assert len(sent) == 1 and sent[0][sent[0].index("--thread") + 1] == SESSION
    assert store.snapshot() == before
    failed, opened = ask(reg, "open_book", {"case_id": case})
    assert not failed and opened["session_binding"]["session_id"] == SESSION
    assert opened["notification_visibility"] == "chat_message"
    reg.close()


@pytest.mark.parametrize("manual", [True, "yes"])
def test_conflicting_or_malformed_manual_mode_creates_nothing(
    tmp_path: Path,
    manual: Any,
) -> None:
    reg, args, _ = prepare(tmp_path)
    failed, _ = ask(reg, "start_case", {**args, "manual_return": manual, "session_id": SESSION})
    assert failed and not list(reg.cases_dir.glob("*.sqlite3"))
