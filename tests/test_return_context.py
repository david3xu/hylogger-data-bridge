# Purpose: exercise durable cross-entry-point return routing and crash-safe notification guards.
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_science import chips

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.cases.dispatch import (
    bind_session,
    check_and_dispatch,
    get_dispatch_path,
    load_session_binding,
)
from hylogger_bridge.cases.registry import CaseRegistry
from hylogger_bridge.cases.return_state import return_state

SESSION = "00000000-0000-4000-8000-000000000001"


def prepared(tmp_path: Path) -> tuple[CaseRegistry, str]:
    workspace = tmp_path / "workspace"
    package = workspace / "nested/FIX001_chips/pkg"
    package.mkdir(parents=True)
    (package / "FIX001_tsg.tsg").write_text("labelled fixture")
    reg = CaseRegistry(
        tmp_path / "cases", None, FixtureProvider(), science=lambda *a: chips(), workspace_auto=True
    )
    case = reg.start_case("nested/FIX001_chips", [5, 10], [0, 5], workspace=workspace)["case_id"]
    return reg, case


def decide(reg: CaseRegistry, case: str) -> dict[str, Any]:
    store = reg.get_store(case)
    page = store.snapshot()["pages"][0]
    return store.decide(
        page["id"],
        page["revision"],
        "accept",
        '[TEST ONLY — not expert validation] exact "note"\n  ',
        "test-return",
    )


def test_new_registry_reads_and_continues_the_exact_durable_case(tmp_path: Path) -> None:
    original, case = prepared(tmp_path)
    state = decide(original, case)
    continuation = state["continuations"][0]
    other = CaseRegistry(
        original.cases_dir, None, FixtureProvider(), science=lambda *a: chips(), workspace_auto=True
    )
    read = other.read_case(case)
    assert read["human_decision_pending"] and read["workspace"].endswith("workspace")
    assert read["pages"][0]["decision"]["id"] == continuation["decision_id"]
    assert read["pages"][0]["decision"]["note"].endswith('"note"\n  ')
    with pytest.raises(ValueError, match="does not match"):
        other.continue_case_tool(case, continuation_id="wrong")
    assert other.get_store(case).snapshot() == state
    result = other.continue_case_tool(
        case, continuation_id=continuation["id"], decision_id=continuation["decision_id"]
    )
    assert result["status"] == "continued" and result["compare"]
    after = other.get_store(case).snapshot()
    replay = other.continue_case_tool(
        case, continuation_id=continuation["id"], decision_id=continuation["decision_id"]
    )
    assert replay["status"] == "already_completed"
    assert after == other.get_store(case).snapshot()
    assert return_state(other.get_store(case))["phase"] == "completed"


def test_repeated_same_session_binding_does_not_reset_attempts(tmp_path: Path) -> None:
    reg, case = prepared(tmp_path)
    decide(reg, case)
    first = bind_session(reg.cases_dir, case, SESSION)
    calls = []

    def fail(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args[0], 1, "", "host unavailable")

    for _ in range(6):
        assert bind_session(reg.cases_dir, case, SESSION) == first
        check_and_dispatch(reg.cases_dir, case, reg.get_store(case), cmd_runner=fail)
    assert len(calls) == 3
    assert load_session_binding(reg.cases_dir, case) == first
    assert return_state(reg.get_store(case))["phase"] == "failed"


def test_corrupt_dispatch_history_never_reinvokes_host(tmp_path: Path) -> None:
    reg, case = prepared(tmp_path)
    decide(reg, case)
    bind_session(reg.cases_dir, case, SESSION)
    get_dispatch_path(reg.cases_dir, case).write_text("broken JSON")

    def forbidden(*a: Any, **k: Any) -> Any:
        pytest.fail("corrupt history must not reset and send")

    with pytest.raises(ValueError, match="unreadable"):
        check_and_dispatch(reg.cases_dir, case, reg.get_store(case), cmd_runner=forbidden)
    assert return_state(reg.get_store(case))["phase"] == "failed"


def test_uncertain_send_is_not_repeated_after_receipt_write_failure(
    tmp_path: Path, monkeypatch: Any
) -> None:
    reg, case = prepared(tmp_path)
    decide(reg, case)
    bind_session(reg.cases_dir, case, SESSION)
    write = Path.write_text
    writes = 0
    calls = []

    def fault(path: Path, text: str, *a: Any, **k: Any) -> int:
        nonlocal writes
        if path.name == f"{case}.dispatch.tmp":
            writes += 1
            if writes == 2:
                raise OSError("simulated disk failure after external send")
        return write(path, text, *a, **k)

    def sent(*a: Any, **k: Any) -> subprocess.CompletedProcess[str]:
        calls.append(a)
        return subprocess.CompletedProcess(a[0], 0, "Queued message test", "")

    monkeypatch.setattr(Path, "write_text", fault)
    result = check_and_dispatch(reg.cases_dir, case, reg.get_store(case), cmd_runner=sent)
    assert result["status"] == "uncertain"
    check_and_dispatch(reg.cases_dir, case, reg.get_store(case), cmd_runner=sent)
    assert len(calls) == 1
    saved = json.loads(get_dispatch_path(reg.cases_dir, case).read_text())
    assert next(iter(saved.values()))["status"] == "in_flight"
    assert return_state(reg.get_store(case))["phase"] == "uncertain"
