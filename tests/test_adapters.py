# Purpose: prove the HTTP and MCP adapters validate their boundary and add no behaviour.
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from collections.abc import Callable
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

from support import (
    SRC,
    BookCase,
    Counting,
    at,
    claim_of,
    completion,
    count,
    decided,
    page_of,
    ready,
    working,
)

from hylogger_bridge.book import BookStore
from hylogger_bridge.book_server import BookServer
from hylogger_bridge.contracts.book import check_book
from hylogger_bridge.contracts.check import validate
from hylogger_bridge.events.runner import RUNNER
from hylogger_bridge.mcp.server import ALL_OPERATIONS, call, handle, serve
from hylogger_bridge.mcp.tools import TOOLS
from hylogger_bridge.walkthrough import LABEL, run


class HttpWorkCase(BookCase):
    def setUp(self) -> None:
        super().setUp()
        self.server = BookServer(0, self.store, self.path.parent)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.stop)

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def post(self, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        headers = {"Content-Type": "application/json"}
        connection.request("POST", path, json.dumps(body), headers)
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload


class HttpWorkTests(HttpWorkCase):
    def test_boundary_refuses_fabricated_attempts_and_unknown_fields(self) -> None:
        decided(self.store)
        status, claimed = self.post("/api/work/claim_delivery", {"worker": "worker-a"})
        self.assertEqual(status, 200)
        handoff = claimed["handoff"]
        base = {"continuation_id": handoff["continuation_id"]}
        for attempt in (0, 11, True, "1", 1.5, None):
            with self.subTest(attempt=attempt):
                status, error = self.post(
                    "/api/work/acknowledge_delivery", {**base, "attempt": attempt}
                )
                self.assertEqual(status, 400)
                validate("Error", error)
                self.assertEqual(error["code"], "invalid_request")
        status, error = self.post("/api/work/acknowledge_delivery", {**base, "attempt": 1, "x": 1})
        self.assertEqual(status, 400)
        status, error = self.post("/api/work/no_such_operation", {})
        self.assertEqual(status, 404)
        status, _ = self.post("/api/work/acknowledge_delivery", {**base, "attempt": 1})
        self.assertEqual(status, 200)

    def test_a_stale_attempt_is_a_conflict_with_a_code(self) -> None:
        decided(self.store)
        self.claim_and_ack("worker-a", 0)
        self.store.claim_delivery("worker-b", at=at(100))
        step = self.step()
        status, error = self.post(
            "/api/work/acknowledge_delivery",
            {"continuation_id": step["id"], "attempt": 1},
        )
        self.assertEqual(status, 409)
        validate("Error", error)
        self.assertEqual(error["code"], "claim_expired")

    def test_unacknowledged_writes_are_refused_over_http(self) -> None:
        _, successor = decided(self.store)
        _, claimed = self.post("/api/work/claim_delivery", {"worker": "worker-a"})
        handoff = claimed["handoff"]
        status, error = self.post("/api/work/submit_result", completion(successor, handoff))
        self.assertEqual(status, 409)
        self.assertEqual(error["code"], "not_ready")

    def test_the_legacy_evidence_route_takes_a_claim(self) -> None:
        _, successor = decided(self.store)
        _, claimed = self.post("/api/work/claim_delivery", {"worker": "worker-a"})
        handoff = claimed["handoff"]
        self.post("/api/work/acknowledge_delivery", claim_of(handoff))
        item = {
            "id": "e1",
            "label": "Note",
            "value": "Observed",
            "source": "Synthetic example",
            "kind": "observation",
        }
        url = f"/api/pages/{successor['id']}/evidence"
        body = {"expected_revision": successor["revision"], "evidence": item}
        status, error = self.post(url, body)
        self.assertEqual((status, error["code"]), (409, "unrelated_page"))
        status, snapshot = self.post(url, {**body, "claim": claim_of(handoff)})
        self.assertEqual(status, 200)
        check_book(snapshot)

    def test_a_delayed_demo_callback_cannot_adopt_a_replacement_run(self) -> None:
        _, successor = decided(self.store)
        held: list[Callable[[], None]] = []
        self.server.launch = held.append
        self.server.demo_delay = 0
        start = {"page_id": successor["id"], "expected_revision": successor["revision"]}
        self.assertEqual(self.post("/api/demo/start", start)[0], 202)
        self.store.recover_interrupted()
        page = working(self.store.snapshot())
        again = {"page_id": page["id"], "expected_revision": page["revision"]}
        self.assertEqual(self.post("/api/demo/start", again)[0], 202)
        old, new = held
        step = self.step()
        self.assertEqual((step["attempts"], step["claimed_by"]), (2, RUNNER))
        before = (self.store.snapshot(), self.store.attempts(step["id"]))
        old()
        self.assertEqual((self.store.snapshot(), self.store.attempts(step["id"])), before)
        new()
        done = self.store.snapshot()
        check_book(done)
        self.assertEqual(page_of(done, successor["id"])["status"], "ready")
        self.assertEqual(self.step()["state"], "completed")
        ended = [row["ended"] for row in self.store.attempts(step["id"])]
        self.assertEqual(ended, ["interrupted", "completed"])

    def test_malformed_candidates_are_invalid_requests_over_http(self) -> None:
        counter = Counting()
        self.store.provider = counter
        page = working(self.store.snapshot())
        before = self.store.snapshot()
        unregistered = {"id": "c", "action_type": "nope_action", "arguments": {}}
        bad: list[Any] = [[None], ["x"], [[]], [5], [{}], [unregistered], "x", {}]
        for candidates in bad:
            with self.subTest(candidates=repr(candidates)):
                body = {
                    "page_id": page["id"],
                    "expected_revision": page["revision"],
                    "candidates": candidates,
                }
                status, error = self.post("/api/work/request_assessment", body)
                self.assertEqual(status, 400)
                validate("Error", error)
                self.assertEqual(error["code"], "invalid_request")
        self.assertEqual(counter.calls, 0)
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(count(self.path, "asks"), 0)

    def test_no_operation_records_a_human_decision(self) -> None:
        self.assertFalse([name for name in ALL_OPERATIONS if "decid" in name or "decision" in name])
        self.assertEqual({tool["name"] for tool in TOOLS}, ALL_OPERATIONS)

    def test_changes_made_elsewhere_reach_the_event_stream(self) -> None:
        page = ready(self.store)
        after = self.store.snapshot()["sequence"]
        stream = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        stream.request("GET", f"/api/events?after={after}")
        response = stream.getresponse()
        other = BookStore(self.path)  # another handle, as a separate worker process would be
        other.decide(page["id"], page["revision"], "accept", "", "elsewhere")
        seen = False
        for _ in range(40):
            if response.readline().startswith(b"event: book_updated"):
                seen = True
                break
        stream.close()
        self.assertTrue(seen)


class WalkthroughTests(unittest.TestCase):
    def test_the_walkthrough_repeats_and_survives_a_reload(self) -> None:
        for _ in range(2):
            with tempfile.TemporaryDirectory() as scratch:
                steps = run(Path(scratch) / "walkthrough.sqlite3")
            whats = [item["what"] for item in steps]
            self.assertEqual(len(steps), 8)
            self.assertIn("A human decision was committed", whats)
            self.assertTrue(steps[2]["exact_note"])
            self.assertEqual(steps[6]["outcome"], "complete")
            self.assertEqual(steps[6]["delivery"], "completed")
            self.assertTrue(steps[-1]["identical"])
        self.assertIn("not Codex continuation", LABEL)


class McpTests(BookCase):
    def ask(self, method: str, params: dict[str, Any] | None = None, ident: int = 1) -> Any:
        message = {"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}
        return handle(self.store, message)

    def tool(self, name: str, arguments: dict[str, Any]) -> tuple[bool, Any]:
        reply = self.ask("tools/call", {"name": name, "arguments": arguments})
        result = reply["result"]
        return result["isError"], json.loads(result["content"][0]["text"])

    def test_handshake_and_listing(self) -> None:
        reply = self.ask("initialize", {"protocolVersion": "2025-03-26"})
        self.assertEqual(reply["result"]["protocolVersion"], "2025-03-26")
        self.assertIn("tools", reply["result"]["capabilities"])
        newer = self.ask("initialize", {"protocolVersion": "2099-01-01"})
        self.assertEqual(newer["result"]["protocolVersion"], "2025-06-18")
        listed = self.ask("tools/list")["result"]["tools"]
        self.assertEqual({tool["name"] for tool in listed}, {tool["name"] for tool in TOOLS})
        self.assertTrue(all(tool["inputSchema"]["type"] == "object" for tool in listed))
        self.assertEqual(self.ask("ping")["result"], {})

    def test_errors_and_notifications(self) -> None:
        self.assertEqual(self.ask("nope")["error"]["code"], -32601)
        unknown = self.ask("tools/call", {"name": "decide", "arguments": {}})
        self.assertEqual(unknown["error"]["code"], -32602)
        note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self.assertIsNone(handle(self.store, note))
        refused = handle(self.store, [])
        assert refused is not None
        self.assertEqual(refused["error"]["code"], -32600)

    def test_tools_carry_a_worker_from_claim_to_ready(self) -> None:
        _, successor = decided(self.store)
        failed, claimed = self.tool("claim_delivery", {"worker": "mcp-worker"})
        self.assertFalse(failed)
        handoff = claimed["handoff"]
        self.assertEqual(handoff["attempt"], 1)
        failed, error = self.tool("acknowledge_delivery", {**claim_of(handoff), "attempt": 7})
        self.assertTrue(failed)
        validate("Error", error)
        failed, _ = self.tool("acknowledge_delivery", claim_of(handoff))
        self.assertFalse(failed)
        failed, advice = self.tool(
            "request_assessment",
            {"page_id": successor["id"], "expected_revision": successor["revision"]},
        )
        self.assertFalse(failed)
        self.assertEqual(working(advice)["assessment"]["origin"], "fixture")
        failed, done = self.tool("submit_result", completion(successor, handoff))
        self.assertFalse(failed)
        check_book(done)
        self.assertEqual(working(done)["status"], "ready")
        failed, again = self.tool("claim_delivery", {"worker": "mcp-worker"})
        self.assertEqual((failed, again["handoff"]), (False, None))

    def test_malformed_candidates_are_tool_errors_without_inference(self) -> None:
        counter = Counting()
        self.store.provider = counter
        page = working(self.store.snapshot())
        before = self.store.snapshot()
        unregistered = {"id": "c", "action_type": "nope_action", "arguments": {}}
        bad: list[Any] = [[None], ["x"], [[]], [5], [{}], [unregistered], "x", {}]
        for candidates in bad:
            with self.subTest(candidates=repr(candidates)):
                arguments = {
                    "page_id": page["id"],
                    "expected_revision": page["revision"],
                    "candidates": candidates,
                }
                failed, error = self.tool("request_assessment", arguments)
                self.assertTrue(failed)
                validate("Error", error)
                self.assertEqual(error["code"], "invalid_request")
        self.assertEqual(counter.calls, 0)
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(count(self.path, "asks"), 0)

    def test_a_refused_tool_call_is_a_result_not_a_crash(self) -> None:
        decided(self.store)
        result = call(self.store, "submit_result", {"anything": 1})
        self.assertTrue(result["isError"])
        failed, body = self.tool("read_attempts", {"continuation_id": "no-such"})
        self.assertEqual((failed, body["code"]), (True, "not_found"))

    def test_serve_writes_only_json_rpc_lines(self) -> None:
        lines = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        source = io.StringIO("\n".join(json.dumps(item) for item in lines) + "\nnot json\n\n")
        sink = io.StringIO()
        serve(self.store, source, sink)
        replies = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(len(replies), 3)
        self.assertEqual([reply["id"] for reply in replies], [1, 2, None])
        self.assertEqual(replies[2]["error"]["code"], -32700)

    def test_the_stdio_process_keeps_stdout_clean(self) -> None:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        script = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        done = subprocess.run(
            [sys.executable, "-m", "hylogger_bridge.mcp.server", "--db", str(self.path)],
            input=script,
            env=env,
            timeout=30,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        (line,) = done.stdout.splitlines()
        self.assertEqual(len(json.loads(line)["result"]["tools"]), len(TOOLS))


if __name__ == "__main__":
    unittest.main()
