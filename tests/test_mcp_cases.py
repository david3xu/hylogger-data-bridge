# Purpose: test MCP case routing, case_id reuse, expert tools, and stdio isolation.
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from support import NOTE, BookCase, working
from test_science import chips

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.cases.registry import CaseRegistry, case_slug, is_valid_case_id
from hylogger_bridge.mcp.server import ALL_OPERATIONS, handle
from hylogger_bridge.mcp.tools import EXPERT_TOOLS, TOOLS


class McpCasesTests(BookCase):
    def setUp(self) -> None:
        super().setUp()
        self.cases_dir = self.path.parent / "test_cases"
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self.data_root = self.path.parent / "test_data_root"
        self.data_root.mkdir(parents=True, exist_ok=True)

        # Create a mock package folder
        self.pkg_id = "MOCK001_chips"
        self.pkg_dir = self.data_root / self.pkg_id / "pkg"
        self.pkg_dir.mkdir(parents=True, exist_ok=True)
        (self.pkg_dir / "MOCK001_chips_tsg.tsg").write_text("header")

        self.hole = chips()
        self.science = lambda f, n: self.hole
        self.provider = FixtureProvider()

        # Track simulated server launches
        self.launched_servers: list[tuple[str, int]] = []

        def mock_launcher(cases_dir: Path, case_id: str, book_path: Path) -> str:
            server_file = cases_dir / f"{case_id}.server.json"
            if server_file.exists():
                data = json.loads(server_file.read_text())
                return f"http://127.0.0.1:{data['port']}"
            port = 9000 + len(self.launched_servers)
            self.launched_servers.append((case_id, port))
            server_file.write_text(json.dumps({"pid": 99999, "port": port}) + "\n")
            return f"http://127.0.0.1:{port}"

        self.registry = CaseRegistry(
            cases_dir=self.cases_dir,
            data_root=self.data_root,
            provider=self.provider,
            science=self.science,
            default_db=self.path,
            server_launcher=mock_launcher,
        )

    def ask(self, method: str, params: dict[str, Any] | None = None, ident: int = 1) -> Any:
        message = {"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}
        return handle(self.registry, message)

    def tool(self, name: str, arguments: dict[str, Any]) -> tuple[bool, Any]:
        reply = self.ask("tools/call", {"name": name, "arguments": arguments})
        result = reply["result"]
        return result["isError"], json.loads(result["content"][0]["text"])

    def test_case_id_slug_and_validation(self) -> None:
        slug = case_slug("SWMB007s_chips", (5.0, 10.0), (0.0, 5.0))
        self.assertEqual(slug, "swmb007s_chips-5_10-vs-0_5")
        self.assertTrue(is_valid_case_id(slug))
        self.assertFalse(is_valid_case_id("../escape"))
        self.assertFalse(is_valid_case_id("invalid/slug"))
        self.assertFalse(is_valid_case_id("-leading-dash"))

    def test_start_case_and_case_id_reuse(self) -> None:
        target = [5.0, 10.0]
        ref = [0.0, 5.0]

        # First call: creates the case
        failed, res1 = self.tool(
            "start_case", {"package_id": self.pkg_id, "target": target, "reference": ref}
        )
        self.assertFalse(failed)
        case_id = res1["case_id"]
        self.assertFalse(res1["reused"])
        self.assertEqual(res1["advice_origin"], "fixture")
        self.assertTrue(len(res1["readable_evidence"]) >= 2)
        book_file = self.cases_dir / f"{case_id}.sqlite3"
        self.assertTrue(book_file.exists())

        store = self.registry.get_store(case_id)
        pages_after_first = store.snapshot()["pages"]
        self.assertEqual(len(pages_after_first), 1)

        # Second call with same parameters: reuses the case without restart or overwrite
        failed, res2 = self.tool(
            "start_case", {"package_id": self.pkg_id, "target": target, "reference": ref}
        )
        self.assertFalse(failed)
        self.assertEqual(res2["case_id"], case_id)
        self.assertTrue(res2["reused"])
        self.assertEqual(len(store.snapshot()["pages"]), 1)

    def test_routing_worker_and_expert_tools_hit_the_same_book(self) -> None:
        target = [5.0, 10.0]
        ref = [0.0, 5.0]

        failed, started = self.tool(
            "start_case", {"package_id": self.pkg_id, "target": target, "reference": ref}
        )
        self.assertFalse(failed)
        case_id = started["case_id"]

        # Read case before decision
        failed, read1 = self.tool("read_case", {"case_id": case_id})
        self.assertFalse(failed)
        self.assertFalse(read1["human_decision_pending"])
        self.assertEqual(len(read1["pages"]), 1)
        self.assertEqual(read1["pages"][0]["status"], "ready")

        # Simulate human committing decision in browser book
        store = self.registry.get_store(case_id)
        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", NOTE, "dec-route-1")

        # Expert tool read_case now shows human_decision_pending: True
        failed, read2 = self.tool("read_case", {"case_id": case_id})
        self.assertFalse(failed)
        self.assertTrue(read2["human_decision_pending"])
        self.assertEqual(read2["pages"][0]["decision"]["choice"], "accept")
        self.assertEqual(read2["pages"][0]["decision"]["note"], NOTE)

        # Worker tool claim_delivery routed to the same case
        failed, claim_res = self.tool("claim_delivery", {"worker": "test-worker", "case": case_id})
        self.assertFalse(failed)
        handoff = claim_res["handoff"]
        self.assertIsNotNone(handoff)
        self.assertEqual(handoff["choice"], "accept")

        # Worker tool acknowledge_delivery on same case
        failed, ack_res = self.tool(
            "acknowledge_delivery",
            {
                "continuation_id": handoff["continuation_id"],
                "attempt": handoff["attempt"],
                "case": case_id,
            },
        )
        self.assertFalse(failed)

    def test_continue_case_with_no_pending_decision_changes_nothing(self) -> None:
        target = [5.0, 10.0]
        ref = [0.0, 5.0]

        failed, started = self.tool(
            "start_case", {"package_id": self.pkg_id, "target": target, "reference": ref}
        )
        self.assertFalse(failed)
        case_id = started["case_id"]
        store = self.registry.get_store(case_id)
        before_snapshot = store.snapshot()

        # Calling continue_case when no decision is committed
        failed, cont_res = self.tool("continue_case", {"case_id": case_id})
        self.assertFalse(failed)
        self.assertEqual(cont_res["status"], "waiting_for_decision")
        self.assertIn("No committed human decision is pending", cont_res["message"])

        # Zero state change
        after_snapshot = store.snapshot()
        self.assertEqual(before_snapshot, after_snapshot)

    def test_continue_case_after_decision_proceeds_to_page_2(self) -> None:
        target = [5.0, 10.0]
        ref = [0.0, 5.0]

        failed, started = self.tool(
            "start_case", {"package_id": self.pkg_id, "target": target, "reference": ref}
        )
        case_id = started["case_id"]
        store = self.registry.get_store(case_id)
        p1 = working(store.snapshot())
        store.decide(p1["id"], p1["revision"], "accept", NOTE, "dec-continue-1")

        # Now continue_case succeeds and returns page 2 readable evidence
        failed, cont_res = self.tool("continue_case", {"case_id": case_id})
        self.assertFalse(failed)
        self.assertEqual(cont_res["status"], "continued")
        self.assertIn("compare", cont_res)
        self.assertTrue(len(cont_res["readable_evidence"]) >= 1)

        # Book now has 2 pages
        snap = store.snapshot()
        self.assertEqual(len(snap["pages"]), 2)
        self.assertEqual(snap["pages"][1]["id"], cont_res["page"])

    def test_no_decision_writing_tool_exists(self) -> None:
        tool_names = [tool["name"] for tool in TOOLS]
        self.assertFalse([name for name in tool_names if "decid" in name or "decision" in name])
        self.assertFalse([name for name in ALL_OPERATIONS if "decid" in name or "decision" in name])

    def test_open_book_server_reuse(self) -> None:
        target = [5.0, 10.0]
        ref = [0.0, 5.0]
        failed, started = self.tool(
            "start_case", {"package_id": self.pkg_id, "target": target, "reference": ref}
        )
        case_id = started["case_id"]

        failed, res1 = self.tool("open_book", {"case_id": case_id})
        self.assertFalse(failed)
        url1 = res1["url"]

        # Second open_book call returns the same running server URL
        failed, res2 = self.tool("open_book", {"case_id": case_id})
        self.assertFalse(failed)
        url2 = res2["url"]
        self.assertEqual(url1, url2)
        self.assertEqual(len(self.launched_servers), 1)

    def test_find_packages_and_list_cases(self) -> None:
        # find_packages
        failed, found = self.tool("find_packages", {})
        self.assertFalse(failed)
        self.assertEqual(len(found["packages"]), 1)
        self.assertEqual(found["packages"][0]["package_id"], self.pkg_id)
        self.assertEqual(found["packages"][0]["hole_id"], "MOCK001")

        # find_packages with matching and non-matching filter
        failed, matched = self.tool("find_packages", {"hole": "MOCK001"})
        self.assertEqual(len(matched["packages"]), 1)
        failed, empty = self.tool("find_packages", {"hole": "NONEXISTENT"})
        self.assertEqual(len(empty["packages"]), 0)

        # list_cases
        failed, listed_before = self.tool("list_cases", {})
        self.assertFalse(failed)

        # start a case and check list_cases again
        self.tool(
            "start_case",
            {"package_id": self.pkg_id, "target": [5.0, 10.0], "reference": [0.0, 5.0]},
        )
        failed, listed_after = self.tool("list_cases", {})
        self.assertFalse(failed)
        self.assertEqual(len(listed_after["cases"]), 1)
        c = listed_after["cases"][0]
        self.assertEqual(c["hole"], "MOCK001")
        self.assertEqual(c["target"], [5.0, 10.0])
        self.assertEqual(c["reference"], [0.0, 5.0])
        self.assertEqual(c["last_page_status"], "ready")

    def test_model_missing_runtime_fails_without_fixture_fallback(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "hylogger_bridge.mcp.server",
            "--model",
            "/nonexistent/model/path",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("error: model folder not found", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_stdout_carries_only_json_rpc(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "hylogger_bridge.mcp.server",
            "--cases",
            str(self.cases_dir),
            "--data-root",
            str(self.data_root),
        ]
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "ping", "params": {}},
        ]
        input_data = "\n".join(json.dumps(m) for m in messages) + "\n"
        proc = subprocess.run(cmd, input=input_data, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 3)
        for line in lines:
            data = json.loads(line)
            self.assertEqual(data.get("jsonrpc"), "2.0")
            self.assertIn("id", data)

    def test_expert_mode_lists_only_expert_tools(self) -> None:
        reply = handle(
            self.registry,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            tools_mode="expert",
        )
        self.assertIsNotNone(reply)
        assert reply is not None
        tools = reply["result"]["tools"]
        self.assertEqual(len(tools), 6)
        names = [t["name"] for t in tools]
        expected = [
            "start_case",
            "read_case",
            "continue_case",
            "open_book",
            "find_packages",
            "list_cases",
        ]
        self.assertEqual(names, expected)
        self.assertEqual(tools, EXPERT_TOOLS)

    def test_expert_mode_refuses_worker_tools(self) -> None:
        for tool_name in ["submit_evidence", "submit_result", "claim_delivery"]:
            reply = handle(
                self.registry,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": {}},
                },
                tools_mode="expert",
            )
            self.assertIsNotNone(reply)
            assert reply is not None
            self.assertIn("error", reply)
            self.assertEqual(reply["error"]["code"], -32602)
            self.assertIn(f"Unknown tool: {tool_name}", reply["error"]["message"])

    def test_cli_expert_tools_option(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "hylogger_bridge.mcp.server",
            "--tools",
            "expert",
            "--cases",
            str(self.cases_dir),
            "--data-root",
            str(self.data_root),
        ]
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "claim_delivery", "arguments": {}},
            },
        ]
        input_data = "\n".join(json.dumps(m) for m in messages) + "\n"
        proc = subprocess.run(cmd, input=input_data, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        resp1 = json.loads(lines[0])
        self.assertEqual(len(resp1["result"]["tools"]), 6)
        resp2 = json.loads(lines[1])
        self.assertEqual(resp2["error"]["code"], -32602)
        self.assertIn("Unknown tool: claim_delivery", resp2["error"]["message"])
