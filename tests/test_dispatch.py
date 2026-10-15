# Purpose: test session binding, durable dispatch tracking, watcher deduplication, and host return.
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from support import NOTE, BookCase, working
from test_science import chips

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.cases.dispatch import (
    MAX_DISPATCH_ATTEMPTS,
    WatcherRegistry,
    bind_session,
    check_and_dispatch,
    is_valid_session_id,
    load_dispatches,
    load_raw_session_binding,
    load_session_binding,
    queue_to_session,
    resolve_codex_bin,
    unbind_session,
)
from hylogger_bridge.cases.registry import CaseRegistry
from hylogger_bridge.mcp.server import WORKSPACE_AUTO, handle

VALID_SESSION_UUID = "01a139d9-409c-7781-91ce-b8bf67aa2103"
ALT_SESSION_UUID = "01a06186-3f83-7511-b612-5847c02d9d0c"


class MockCommandRunner:
    def __init__(
        self,
        returncode: int = 0,
        stdout: str = (
            "Queued message 01a13ec3-ab5e-7142-a019-2a7ea5fbf3ec for thread "
            "01a139d9-409c-7781-91ce-b8bf67aa2103.\n"
        ),
        stderr: str = "",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[list[str]] = []
        self._lock = threading.Lock()

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        with self._lock:
            self.calls.append(cmd)
            # Sleep briefly to simulate process execution and test race conditions
            time.sleep(0.01)
            return subprocess.CompletedProcess(
                cmd, self.returncode, stdout=self.stdout, stderr=self.stderr
            )


class DispatchTests(BookCase):
    def setUp(self) -> None:
        super().setUp()
        self.cases_dir = self.path.parent / "dispatch_test_cases"
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self.data_root = self.path.parent / "dispatch_test_data"
        self.data_root.mkdir(parents=True, exist_ok=True)

        self.pkg_id = "SWMB007s_chips"
        self.pkg_dir = self.data_root / self.pkg_id / "pkg"
        self.pkg_dir.mkdir(parents=True, exist_ok=True)
        (self.pkg_dir / "SWMB007s_chips_tsg.tsg").write_text("header")

        self.hole = chips()
        self.science = lambda f, n: self.hole
        self.provider = FixtureProvider()
        self.cmd_runner = MockCommandRunner()

        self.registry = CaseRegistry(
            cases_dir=self.cases_dir,
            data_root=self.data_root,
            provider=self.provider,
            science=self.science,
            cmd_runner=self.cmd_runner,
            watcher_interval=0.05,
        )

    def tearDown(self) -> None:
        self.registry.close()
        super().tearDown()

    def test_session_id_validation(self) -> None:
        self.assertTrue(is_valid_session_id(VALID_SESSION_UUID))
        self.assertTrue(is_valid_session_id(ALT_SESSION_UUID))
        self.assertTrue(is_valid_session_id("41a34091-2ee0-4b53-a8ce-8eb8c3209f58"))
        self.assertTrue(is_valid_session_id("41a340912ee04b53a8ce8eb8c3209f58"))

        self.assertFalse(is_valid_session_id(""))
        self.assertFalse(is_valid_session_id("not-a-uuid"))
        self.assertFalse(is_valid_session_id("   "))
        self.assertFalse(is_valid_session_id("12345"))
        self.assertFalse(is_valid_session_id("; rm -rf / ;"))

    def test_bind_and_unbind_session(self) -> None:
        case_id = "test-hole-10_20-vs-30_40"
        binding = bind_session(self.cases_dir, case_id, VALID_SESSION_UUID)
        self.assertEqual(binding["case_id"], case_id)
        self.assertEqual(binding["session_id"], VALID_SESSION_UUID)
        self.assertTrue(binding["active"])

        # Reload from disk
        loaded = load_session_binding(self.cases_dir, case_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["session_id"], VALID_SESSION_UUID)
        self.assertTrue(loaded["active"])

        # Unbind
        unbound = unbind_session(self.cases_dir, case_id)
        self.assertFalse(unbound["active"])
        self.assertIsNone(load_session_binding(self.cases_dir, case_id))

        # Invalid session UUID raises ValueError
        with self.assertRaises(ValueError):
            bind_session(self.cases_dir, case_id, "invalid-uuid")

        # Invalid case ID raises ValueError
        with self.assertRaises(ValueError):
            bind_session(self.cases_dir, "bad/case/id", VALID_SESSION_UUID)

    def test_queue_to_session_runner(self) -> None:
        ok, out, msg_id = queue_to_session(
            VALID_SESSION_UUID, "test message", cmd_runner=self.cmd_runner
        )
        self.assertTrue(ok)
        self.assertEqual(msg_id, "01a13ec3-ab5e-7142-a019-2a7ea5fbf3ec")
        self.assertEqual(len(self.cmd_runner.calls), 1)
        self.assertEqual(
            self.cmd_runner.calls[0][1:],
            ["queue", "--thread", VALID_SESSION_UUID, "--message", "test message"],
        )
        self.assertTrue(self.cmd_runner.calls[0][0].endswith("codex"))

        # Failure handling
        failing_runner = MockCommandRunner(returncode=1, stdout="", stderr="Session not found\n")
        ok_fail, err, msg_id_fail = queue_to_session(
            VALID_SESSION_UUID, "test", cmd_runner=failing_runner
        )
        self.assertFalse(ok_fail)
        self.assertEqual(err, "Session not found")
        self.assertIsNone(msg_id_fail)

    def test_check_and_dispatch_idle_and_unbound_make_zero_calls(self) -> None:
        started = self.registry.start_case(self.pkg_id, [10.0, 20.0], [30.0, 40.0])
        case_id = started["case_id"]
        store = self.registry.get_store(case_id)

        # 1. Unbound case makes 0 calls
        res_unbound = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(res_unbound["status"], "not_bound")
        self.assertEqual(len(self.cmd_runner.calls), 0)

        # 2. Bound case with NO pending continuations makes 0 calls (idle)
        self.registry.bind_case(case_id, VALID_SESSION_UUID)
        res_idle = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(res_idle["status"], "idle")
        self.assertEqual(len(self.cmd_runner.calls), 0)

    def test_check_and_dispatch_idempotent_duplicate_prevention(self) -> None:
        started = self.registry.start_case(self.pkg_id, [10.0, 20.0], [30.0, 40.0])
        case_id = started["case_id"]
        bind_session(self.cases_dir, case_id, VALID_SESSION_UUID)
        store = self.registry.get_store(case_id)

        # Simulate human committing decision in browser book
        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", NOTE, "req-test-1")

        # First check_and_dispatch: pending continuation found -> dispatched
        res1 = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(res1["status"], "dispatched")
        self.assertEqual(res1["dispatched"], 1)
        self.assertEqual(len(self.cmd_runner.calls), 1)

        # Message format check
        sent_msg = self.cmd_runner.calls[0][5]
        self.assertIn("[HyLogger Return]", sent_msg)
        self.assertIn(case_id, sent_msg)
        self.assertIn("read_case", sent_msg)
        self.assertIn("continue_case", sent_msg)
        self.assertIn("user review preferences", sent_msg)

        # Verify durable dispatch record
        dispatches = load_dispatches(self.cases_dir, case_id)
        self.assertEqual(len(dispatches), 1)
        rec = next(iter(dispatches.values()))
        self.assertEqual(rec["status"], "dispatched")
        self.assertEqual(rec["attempts"], 1)
        self.assertEqual(rec["message_id"], "01a13ec3-ab5e-7142-a019-2a7ea5fbf3ec")

        # Second check_and_dispatch: already dispatched -> 0 additional calls!
        res2 = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(res2["dispatched"], 0)
        self.assertEqual(len(self.cmd_runner.calls), 1)

    def test_check_and_dispatch_bounded_retries(self) -> None:
        # Start without session_id so registry background watcher is not running for this case
        started = self.registry.start_case(self.pkg_id, [10.0, 20.0], [30.0, 40.0])
        case_id = started["case_id"]
        bind_session(self.cases_dir, case_id, VALID_SESSION_UUID)
        store = self.registry.get_store(case_id)

        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", NOTE, "req-fail-1")

        failing_runner = MockCommandRunner(returncode=1, stdout="", stderr="queue unavailable")

        # Dispatch attempts 1, 2, 3 fail
        for attempt in range(1, MAX_DISPATCH_ATTEMPTS + 1):
            res = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=failing_runner)
            self.assertEqual(res["dispatched"], 0)
            self.assertEqual(len(failing_runner.calls), attempt)
            dispatches = load_dispatches(self.cases_dir, case_id)
            rec = next(iter(dispatches.values()))
            self.assertEqual(rec["status"], "failed")
            self.assertEqual(rec["attempts"], attempt)
            self.assertEqual(rec["last_error"], "queue unavailable")

        # Attempt 4: MAX_DISPATCH_ATTEMPTS exceeded -> skips calling runner!
        res4 = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=failing_runner)
        self.assertEqual(res4["dispatched"], 0)
        self.assertEqual(len(failing_runner.calls), MAX_DISPATCH_ATTEMPTS)

    def test_competing_watchers_concurrency(self) -> None:
        # Start without session_id so registry background watcher is not running for this case
        started = self.registry.start_case(self.pkg_id, [10.0, 20.0], [30.0, 40.0])
        case_id = started["case_id"]
        bind_session(self.cases_dir, case_id, VALID_SESSION_UUID)
        store = self.registry.get_store(case_id)

        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", NOTE, "req-race-1")

        # Run 5 concurrent threads executing check_and_dispatch simultaneously
        threads = []
        for _ in range(5):
            t = threading.Thread(
                target=lambda: check_and_dispatch(
                    self.cases_dir, case_id, store, cmd_runner=self.cmd_runner
                )
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly ONE call was made despite 5 concurrent callers
        self.assertEqual(len(self.cmd_runner.calls), 1)

    def test_watcher_registry_deduplication(self) -> None:
        watcher_reg = WatcherRegistry()
        case_id = "test-case-watch"

        w1 = watcher_reg.start_watcher(
            self.cases_dir,
            case_id,
            lambda: self.registry.get_store(),
            interval=0.1,
            cmd_runner=self.cmd_runner,
        )
        self.assertTrue(w1.is_alive)

        # Starting again on the same case returns the same watcher instance
        w2 = watcher_reg.start_watcher(
            self.cases_dir,
            case_id,
            lambda: self.registry.get_store(),
            interval=0.1,
            cmd_runner=self.cmd_runner,
        )
        self.assertIs(w1, w2)

        watcher_reg.stop_watcher(case_id)
        self.assertFalse(w1.is_alive)
        watcher_reg.stop_all()

    def test_registry_full_lifecycle_with_return(self) -> None:
        # 1. Start case with session_id
        started = self.registry.start_case(
            self.pkg_id, [10.0, 20.0], [30.0, 40.0], session_id=VALID_SESSION_UUID
        )
        case_id = started["case_id"]
        self.assertIn("session_binding", started)
        self.assertEqual(started["session_binding"]["session_id"], VALID_SESSION_UUID)

        # 2. Read case initially shows no pending decision
        read1 = self.registry.read_case(case_id)
        self.assertFalse(read1["human_decision_pending"])
        self.assertIsNotNone(read1["session_binding"])
        self.assertEqual(len(read1["dispatches"]), 0)

        # 3. Simulate human expert committing decision in the browser book
        test_note = "[TEST DECISION — not expert validation] Verified interval comparison"
        store = self.registry.get_store(case_id)
        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", test_note, "req-human-dec-1")

        # 4. Wait for background watcher to dispatch automatically
        deadline = time.time() + 2.0
        while time.time() < deadline:
            dispatches = load_dispatches(self.cases_dir, case_id)
            if dispatches and next(iter(dispatches.values()))["status"] == "dispatched":
                break
            time.sleep(0.01)
        self.assertEqual(len(self.cmd_runner.calls), 1)

        # 5. read_case now shows human_decision_pending: True and the recorded dispatch
        read2 = self.registry.read_case(case_id)
        self.assertTrue(read2["human_decision_pending"])
        self.assertEqual(read2["pages"][0]["decision"]["choice"], "accept")
        self.assertEqual(read2["pages"][0]["decision"]["note"], test_note)
        self.assertEqual(len(read2["dispatches"]), 1)
        self.assertEqual(read2["dispatches"][0]["status"], "dispatched")

        # 6. continue_case claims delivery and completes Page 2
        cont_res = self.registry.continue_case_tool(case_id)
        self.assertEqual(cont_res["status"], "continued")
        self.assertTrue(cont_res["page"])

        # 7. read_case now shows human_decision_pending: False
        read3 = self.registry.read_case(case_id)
        self.assertFalse(read3["human_decision_pending"])
        self.assertEqual(len(read3["pages"]), 2)
        self.assertEqual(read3["pages"][1]["status"], "ready")

        # 8. Subsequent check makes 0 calls
        calls_before = len(self.cmd_runner.calls)
        check_after = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(check_after["dispatched"], 0)
        self.assertEqual(len(self.cmd_runner.calls), calls_before)

    def test_mcp_binding_operations(self) -> None:
        # Call start_case with session_id via MCP handle
        reply_start = handle(
            self.registry,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "start_case",
                    "arguments": {
                        "package_id": self.pkg_id,
                        "target": [10.0, 20.0],
                        "reference": [30.0, 40.0],
                        "session_id": VALID_SESSION_UUID,
                    },
                },
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply_start)
        assert reply_start is not None
        self.assertFalse(reply_start["result"]["isError"])
        content_start = json.loads(reply_start["result"]["content"][0]["text"])
        case_id = content_start["case_id"]
        self.assertIn("session_binding", content_start)
        self.assertEqual(content_start["session_binding"]["session_id"], VALID_SESSION_UUID)

        # Call read_case via MCP handle
        reply_read = handle(
            self.registry,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "read_case", "arguments": {"case_id": case_id}},
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply_read)
        assert reply_read is not None
        content_read = json.loads(reply_read["result"]["content"][0]["text"])
        self.assertEqual(content_read["session_binding"]["session_id"], VALID_SESSION_UUID)

        # Test unbind and re-bind via registry methods
        unbound = self.registry.unbind_case(case_id)
        self.assertFalse(unbound["active"])
        self.assertIsNone(self.registry.read_case(case_id)["session_binding"])

        rebound = self.registry.bind_case(case_id, ALT_SESSION_UUID)
        self.assertTrue(rebound["active"])
        self.assertEqual(
            self.registry.read_case(case_id)["session_binding"]["session_id"], ALT_SESSION_UUID
        )

    def test_workspace_discovery_nested(self) -> None:
        ws = self.path.parent / "custom_ws"
        # Nested package
        nested_pkg = ws / "projects" / "2024" / "drill_deep" / "pkg"
        nested_pkg.mkdir(parents=True, exist_ok=True)
        (nested_pkg / "drill_deep_tsg.tsg").write_text("header")

        # Flat package
        flat_pkg = ws / "top_level_pkg" / "pkg"
        flat_pkg.mkdir(parents=True, exist_ok=True)
        (flat_pkg / "top_level_pkg_tsg.tsg").write_text("header")

        # Discover all packages in workspace
        res = self.registry.find_packages_tool(workspace=ws)
        pkg_ids = [p["package_id"] for p in res["packages"]]
        self.assertIn("projects/2024/drill_deep", pkg_ids)
        self.assertIn("top_level_pkg", pkg_ids)

        # Filter by hole
        res_hole = self.registry.find_packages_tool(hole="drill", workspace=ws)
        self.assertEqual(len(res_hole["packages"]), 1)
        self.assertEqual(res_hole["packages"][0]["package_id"], "projects/2024/drill_deep")

        # Via MCP handle
        reply = handle(
            self.registry,
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "find_packages",
                    "arguments": {"workspace": str(ws), "hole": "top"},
                },
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertFalse(reply["result"]["isError"])
        content = json.loads(reply["result"]["content"][0]["text"])
        self.assertEqual(len(content["packages"]), 1)
        self.assertEqual(content["packages"][0]["package_id"], "top_level_pkg")

    def test_workspace_case_isolation(self) -> None:
        ws1 = self.path.parent / "ws1"
        ws2 = self.path.parent / "ws2"
        pkg1 = ws1 / "shared_hole" / "pkg"
        pkg2 = ws2 / "shared_hole" / "pkg"
        pkg1.mkdir(parents=True, exist_ok=True)
        pkg2.mkdir(parents=True, exist_ok=True)
        (pkg1 / "shared_hole_tsg.tsg").write_text("header")
        (pkg2 / "shared_hole_tsg.tsg").write_text("header")

        # Start cases in both workspaces with identical hole name and interval bounds
        res1 = self.registry.start_case("shared_hole", [10.0, 20.0], [30.0, 40.0], workspace=ws1)
        res2 = self.registry.start_case("shared_hole", [10.0, 20.0], [30.0, 40.0], workspace=ws2)

        # Case IDs must be distinct due to different workspace paths
        self.assertNotEqual(res1["case_id"], res2["case_id"])

        # list_cases filtered by workspace
        list_ws1 = self.registry.list_cases_tool(workspace=ws1)
        case_ids_ws1 = [c["case_id"] for c in list_ws1["cases"]]
        self.assertIn(res1["case_id"], case_ids_ws1)
        self.assertNotIn(res2["case_id"], case_ids_ws1)

        list_ws2 = self.registry.list_cases_tool(workspace=ws2)
        case_ids_ws2 = [c["case_id"] for c in list_ws2["cases"]]
        self.assertIn(res2["case_id"], case_ids_ws2)
        self.assertNotIn(res1["case_id"], case_ids_ws2)

        # list_cases without workspace returns both
        list_all = self.registry.list_cases_tool()
        case_ids_all = [c["case_id"] for c in list_all["cases"]]
        self.assertIn(res1["case_id"], case_ids_all)
        self.assertIn(res2["case_id"], case_ids_all)

    def test_workspace_access_revalidation(self) -> None:
        ws1 = self.path.parent / "ws_reval_1"
        ws2 = self.path.parent / "ws_reval_2"
        ws3 = self.path.parent / "ws_reval_3"
        ws2.mkdir(parents=True, exist_ok=True)
        ws3.mkdir(parents=True, exist_ok=True)

        pkg1 = ws1 / "reval_hole" / "pkg"
        pkg1.mkdir(parents=True, exist_ok=True)
        (pkg1 / "reval_hole_tsg.tsg").write_text("header")

        # ws2 has hole with same name but different folder
        pkg2 = ws2 / "reval_hole" / "pkg"
        pkg2.mkdir(parents=True, exist_ok=True)
        (pkg2 / "reval_hole_tsg.tsg").write_text("header")

        res = self.registry.start_case("reval_hole", [10.0, 20.0], [30.0, 40.0], workspace=ws1)
        case_id = res["case_id"]

        # Commit test decision
        store = self.registry.get_store(case_id)
        p1 = working(store.snapshot())
        store.decide(
            p1["id"],
            p1["revision"],
            "accept",
            "[TEST DECISION — not expert validation] Revalidation test",
            "req-reval-1",
        )

        # Revalidation fails when package is missing in workspace
        with self.assertRaises(ValueError) as ctx:
            self.registry.continue_case_tool(case_id, workspace=ws3)
        self.assertIn(
            "Continuation workspace differs from the original case workspace", str(ctx.exception)
        )

        # Revalidation fails when workspace package folder does not match original stored
        # scene folder
        with self.assertRaises(ValueError) as ctx:
            self.registry.continue_case_tool(case_id, workspace=ws2)
        self.assertIn(
            "Continuation workspace differs from the original case workspace", str(ctx.exception)
        )

        # Revalidation succeeds when correct workspace is provided
        cont_res = self.registry.continue_case_tool(case_id, workspace=ws1)
        self.assertEqual(cont_res["status"], "continued")

    def test_workspace_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.registry.resolve_workspace("")
        self.assertIn("workspace cannot be empty", str(ctx.exception))

        with self.assertRaises(ValueError):
            self.registry.resolve_workspace("   ")

        missing = self.path.parent / "nonexistent_workspace_dir"
        with self.assertRaises(ValueError) as ctx:
            self.registry.resolve_workspace(missing)
        self.assertIn("does not exist or is not a directory", str(ctx.exception))

        dummy_file = self.path.parent / "file_not_dir.txt"
        dummy_file.write_text("sample")
        with self.assertRaises(ValueError) as ctx:
            self.registry.resolve_workspace(dummy_file)
        self.assertIn("does not exist or is not a directory", str(ctx.exception))

    def test_mcp_workspace_full_flow(self) -> None:
        ws = self.path.parent / "ws_mcp"
        pkg = ws / "mcp_hole" / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "mcp_hole_tsg.tsg").write_text("header")

        # 1. start_case via MCP with workspace
        reply_start = handle(
            self.registry,
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {
                    "name": "start_case",
                    "arguments": {
                        "package_id": "mcp_hole",
                        "manual_return": True,
                        "target": [10.0, 20.0],
                        "reference": [30.0, 40.0],
                        "workspace": str(ws),
                    },
                },
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply_start)
        assert reply_start is not None
        self.assertFalse(reply_start["result"]["isError"])
        case_id = json.loads(reply_start["result"]["content"][0]["text"])["case_id"]

        # 2. list_cases via MCP with workspace
        reply_list = handle(
            self.registry,
            {
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {
                    "name": "list_cases",
                    "arguments": {"workspace": str(ws)},
                },
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply_list)
        assert reply_list is not None
        cases = json.loads(reply_list["result"]["content"][0]["text"])["cases"]
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["case_id"], case_id)

        # 3. Commit decision in store
        store = self.registry.get_store(case_id)
        p1 = working(store.snapshot())
        store.decide(
            p1["id"],
            p1["revision"],
            "accept",
            "[TEST DECISION — not expert validation] MCP flow test",
            "req-mcp-flow-1",
        )

        # 4. continue_case via MCP with workspace
        reply_cont = handle(
            self.registry,
            {
                "jsonrpc": "2.0",
                "id": 22,
                "method": "tools/call",
                "params": {
                    "name": "continue_case",
                    "arguments": {"case_id": case_id, "workspace": str(ws)},
                },
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply_cont)
        assert reply_cont is not None
        cont_content = json.loads(reply_cont["result"]["content"][0]["text"])
        self.assertEqual(cont_content["status"], "continued")

    def test_workspace_auto_mode(self) -> None:
        self.assertTrue(WORKSPACE_AUTO)
        reg_auto = CaseRegistry(
            cases_dir=self.cases_dir,
            data_root=None,
            provider=self.provider,
            science=self.science,
            cmd_runner=self.cmd_runner,
            workspace_auto=True,
        )
        self.assertTrue(reg_auto.workspace_auto)
        self.assertIsNone(reg_auto.data_root)

        # Missing workspace raises ValueError
        with self.assertRaises(ValueError) as ctx:
            reg_auto.resolve_workspace(None)
        self.assertIn("No authorised workspace provided", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx_find:
            reg_auto.find_packages_tool()
        self.assertIn("No authorised workspace provided", str(ctx_find.exception))

        # Providing workspace succeeds
        ws = self.path.parent / "ws_auto_test"
        pkg = ws / "auto_hole" / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "auto_hole_tsg.tsg").write_text("header")

        resolved = reg_auto.resolve_workspace(ws)
        self.assertEqual(resolved, ws.resolve())

        found = reg_auto.find_packages_tool(workspace=ws)
        self.assertEqual(len(found["packages"]), 1)
        self.assertEqual(found["packages"][0]["package_id"], "auto_hole")

        started = reg_auto.start_case("auto_hole", [10.0, 20.0], [30.0, 40.0], workspace=ws)
        self.assertTrue(started["case_id"])
        self.assertIn(str(ws.resolve()), started.get("workspace", ""))

    def test_workspace_auto_host_meta_injection(self) -> None:
        reg_auto = CaseRegistry(
            cases_dir=self.cases_dir,
            data_root=None,
            provider=self.provider,
            science=self.science,
            cmd_runner=self.cmd_runner,
            workspace_auto=True,
        )
        ws = self.path.parent / "ws_meta_test"
        pkg = ws / "meta_hole" / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "meta_hole_tsg.tsg").write_text("header")

        # When host passes workspace inside _meta or params root
        reply = handle(
            reg_auto,
            {
                "jsonrpc": "2.0",
                "id": 40,
                "method": "tools/call",
                "params": {
                    "name": "find_packages",
                    "arguments": {},
                    "_meta": {"workspace": str(ws)},
                },
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertFalse(reply["result"]["isError"])
        content = json.loads(reply["result"]["content"][0]["text"])
        self.assertEqual(len(content["packages"]), 1)
        self.assertEqual(content["packages"][0]["package_id"], "meta_hole")

    def test_pre_reservation_storage_failure(self) -> None:
        started = self.registry.start_case(self.pkg_id, [10.0, 20.0], [30.0, 40.0])
        case_id = started["case_id"]
        bind_session(self.cases_dir, case_id, VALID_SESSION_UUID)
        store = self.registry.get_store(case_id)
        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", NOTE, "req-disk-fail")

        orig_write_text = Path.write_text
        fail_disk = True

        def mock_write_text(path_self: Path, data: str, *args: Any, **kwargs: Any) -> int:
            if fail_disk and (".dispatch." in path_self.name and path_self.name.endswith(".tmp")):
                raise OSError("simulated full disk")
            return orig_write_text(path_self, data, *args, **kwargs)

        with patch.object(Path, "write_text", side_effect=mock_write_text, autospec=True):
            for _ in range(4):
                with self.assertRaises(OSError):
                    check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
            # cmd_runner was never called because reservation failed before dispatch
            self.assertEqual(len(self.cmd_runner.calls), 0)

        # Restore write: recovery succeeds and respects MAX_DISPATCH_ATTEMPTS
        failing_runner = MockCommandRunner(returncode=1, stdout="", stderr="host down")
        for attempt in range(1, MAX_DISPATCH_ATTEMPTS + 1):
            res = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=failing_runner)
            self.assertEqual(res["dispatched"], 0)
            self.assertEqual(len(failing_runner.calls), attempt)

        # Attempt 4 is bounded
        res4 = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=failing_runner)
        self.assertEqual(res4["dispatched"], 0)
        self.assertEqual(len(failing_runner.calls), MAX_DISPATCH_ATTEMPTS)

    def test_fenced_rebinding_and_generation(self) -> None:
        started = self.registry.start_case(self.pkg_id, [10.0, 20.0], [30.0, 40.0])
        case_id = started["case_id"]
        store = self.registry.get_store(case_id)

        # Bind S1 (generation 1)
        bind_session(self.cases_dir, case_id, VALID_SESSION_UUID)
        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", NOTE, "req-fenced-1")

        # Dispatch 1: call to S1
        res1 = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(res1["dispatched"], 1)
        self.assertEqual(len(self.cmd_runner.calls), 1)
        self.assertIn(VALID_SESSION_UUID, self.cmd_runner.calls[0])

        # Rebind S2 while still pending
        bind_session(self.cases_dir, case_id, ALT_SESSION_UUID)
        raw_b2 = load_raw_session_binding(self.cases_dir, case_id)
        self.assertIsNotNone(raw_b2)
        assert raw_b2 is not None
        self.assertEqual(raw_b2["generation"], 2)

        # Dispatch to S2: 1 call to S2
        res2 = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(res2["dispatched"], 1)
        self.assertEqual(len(self.cmd_runner.calls), 2)
        self.assertIn(ALT_SESSION_UUID, self.cmd_runner.calls[1])

        # Receipts for both S1 and S2 are preserved
        dispatches = load_dispatches(self.cases_dir, case_id)
        self.assertEqual(len(dispatches), 2)
        self.assertTrue(
            any(
                r["session_id"] == VALID_SESSION_UUID and r["status"] == "dispatched"
                for r in dispatches.values()
            )
        )
        self.assertTrue(
            any(
                r["session_id"] == ALT_SESSION_UUID and r["status"] == "dispatched"
                for r in dispatches.values()
            )
        )

        # Check again: 0 calls
        res3 = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(res3["dispatched"], 0)
        self.assertEqual(len(self.cmd_runner.calls), 2)

        # Complete continuation
        self.registry.continue_case_tool(case_id)

        # Rebind S3: 0 calls
        s3_uuid = "41a34091-2ee0-4b53-a8ce-8eb8c3209f58"
        bind_session(self.cases_dir, case_id, s3_uuid)
        res4 = check_and_dispatch(self.cases_dir, case_id, store, cmd_runner=self.cmd_runner)
        self.assertEqual(res4["dispatched"], 0)
        self.assertEqual(len(self.cmd_runner.calls), 2)

        # Test unbind-before-send: 0 calls, not_bound
        s2_case = self.registry.start_case(self.pkg_id, [20.0, 30.0], [40.0, 50.0])
        c2_id = s2_case["case_id"]
        c2_store = self.registry.get_store(c2_id)
        bind_session(self.cases_dir, c2_id, VALID_SESSION_UUID)
        c2_p1 = working(c2_store.snapshot())
        c2_store.decide(c2_p1["id"], c2_p1["revision"], "accept", NOTE, "req-unbind-before-send")

        unbind_session(self.cases_dir, c2_id)
        res_unbound = check_and_dispatch(
            self.cases_dir, c2_id, c2_store, cmd_runner=self.cmd_runner
        )
        self.assertEqual(res_unbound["status"], "not_bound")
        self.assertEqual(res_unbound["dispatched"], 0)
        self.assertEqual(len(self.cmd_runner.calls), 2)

    def test_expert_unbind_tool(self) -> None:
        started = self.registry.start_case(
            self.pkg_id, [10.0, 20.0], [30.0, 40.0], session_id=VALID_SESSION_UUID
        )
        case_id = started["case_id"]
        self.assertIsNotNone(load_session_binding(self.cases_dir, case_id))
        self.assertTrue(self.registry._watchers.is_watching(case_id))

        # Call read_case with unbind=True via MCP handle
        reply = handle(
            self.registry,
            {
                "jsonrpc": "2.0",
                "id": 51,
                "method": "tools/call",
                "params": {
                    "name": "read_case",
                    "arguments": {"case_id": case_id, "unbind": True},
                },
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertFalse(reply["result"]["isError"])
        content = json.loads(reply["result"]["content"][0]["text"])
        self.assertIsNone(content.get("session_binding"))
        self.assertIsNone(load_session_binding(self.cases_dir, case_id))
        self.assertFalse(self.registry._watchers.is_watching(case_id))

        # Also test continue_case with unbind=True via MCP handle
        bind_session(self.cases_dir, case_id, ALT_SESSION_UUID)
        self.registry._start_watcher_if_bound(case_id)
        self.assertIsNotNone(load_session_binding(self.cases_dir, case_id))

        store = self.registry.get_store(case_id)
        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", NOTE, "req-unbind-cont")

        reply_cont = handle(
            self.registry,
            {
                "jsonrpc": "2.0",
                "id": 52,
                "method": "tools/call",
                "params": {
                    "name": "continue_case",
                    "arguments": {"case_id": case_id, "unbind": True},
                },
            },
            tools_mode="expert",
        )
        self.assertIsNotNone(reply_cont)
        assert reply_cont is not None
        self.assertFalse(reply_cont["result"]["isError"])
        self.assertIsNone(load_session_binding(self.cases_dir, case_id))
        self.assertFalse(self.registry._watchers.is_watching(case_id))

    def test_host_executable_resolution_spaces_and_minimal_path(self) -> None:
        spaced_dir = self.path.parent / "bin with spaces"
        spaced_dir.mkdir(parents=True, exist_ok=True)
        fake_codex = spaced_dir / "fake codex"
        fake_codex.write_text(
            '#!/bin/sh\necho "Queued message 01a13ec3-ab5e-7142-a019-2a7ea5fbf3ec for thread $3."\n'
        )
        fake_codex.chmod(0o755)

        with patch.dict(os.environ, {"HYLOGGER_CODEX": str(fake_codex)}):
            resolved = resolve_codex_bin()
            self.assertEqual(resolved, str(fake_codex))

            ok, out, msg_id = queue_to_session(
                VALID_SESSION_UUID, "test spaces msg", cmd_runner=subprocess.run
            )
            self.assertTrue(ok)
            self.assertEqual(msg_id, "01a13ec3-ab5e-7142-a019-2a7ea5fbf3ec")

        with patch.dict(os.environ, {"PATH": "/nonexistent", "HYLOGGER_CODEX": ""}):
            with patch("shutil.which", return_value=None):
                with patch("pathlib.Path.is_file", return_value=False):
                    self.assertIsNone(resolve_codex_bin())
                    ok_miss, err_miss, msg_id_miss = queue_to_session(VALID_SESSION_UUID, "msg")
                    self.assertFalse(ok_miss)
                    self.assertIn("Host executable 'codex' not found", err_miss)
                    self.assertIsNone(msg_id_miss)
