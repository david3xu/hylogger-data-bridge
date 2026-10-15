# Purpose: exercise the real expert MCP surface using disposable books and owned processes.
import json
import os
import select
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def run(repo: Path, cases: Path) -> dict[str, Any]:
    launcher = repo / "plugins/hylogger/bin/hylogger-mcp"
    env = {**os.environ, "HYLOGGER_HOME": str(repo), "HYLOGGER_FIXTURE": "1"}
    proc = subprocess.Popen(
        [str(launcher), "--cases", str(cases)],
        cwd="/tmp",
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdin is not None and proc.stdout is not None
        serial = 0

        def ask(method: str, params: dict[str, Any] | None = None) -> Any:
            nonlocal serial
            serial += 1
            assert proc.stdin is not None and proc.stdout is not None
            message = {"jsonrpc": "2.0", "id": serial, "method": method, "params": params or {}}
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()
            if not select.select([proc.stdout], [], [], 20)[0]:
                raise RuntimeError("MCP smoke request timed out")
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP process exited; check science environment/UI prerequisites")
            reply = json.loads(line)
            if "error" in reply:
                raise RuntimeError(str(reply["error"]))
            return reply["result"]

        def tool(name: str, arguments: dict[str, Any]) -> Any:
            reply = ask("tools/call", {"name": name, "arguments": arguments})
            if reply["isError"]:
                raise RuntimeError(str(reply["content"]))
            return json.loads(reply["content"][0]["text"])

        ask("initialize")
        names = [t["name"] for t in ask("tools/list")["tools"]]
        assert names == [
            "start_case",
            "read_case",
            "continue_case",
            "open_book",
            "find_packages",
            "list_cases",
        ]
        found = tool("find_packages", {"hole": "SWMB007s"})
        assert found["packages"]
        assert tool("list_cases", {})["cases"] == []
        args = {"package_id": "SWMB007s_chips", "target": [5.0, 10.0], "reference": [0.0, 5.0]}
        first = tool("start_case", args)
        assert first["status"] == "ready" and first["advice_origin"] == "fixture"
        assert tool("start_case", args)["reused"] is True
        case = {"case_id": first["case_id"]}
        opened = tool("open_book", case)
        assert tool("open_book", case)["url"] == opened["url"]
        read = tool("read_case", case)
        assert read["pages"][0]["status"] == "ready" and not read["human_decision_pending"]
        assert tool("continue_case", case)["status"] == "waiting_for_decision"
        return {"tools": names, "case": first, "book": opened, "read": read}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        # This fresh registry was created exclusively for this run. Never inspect a user registry.
        for record in cases.glob("*.server.json"):
            try:
                os.kill(int(json.loads(record.read_text())["pid"]), signal.SIGTERM)
            except (OSError, ValueError, KeyError):
                pass


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="hylogger-smoke-") as temporary:
        report = run(repo, Path(temporary))
        print(json.dumps(report, indent=2))
        print("Smoke passed with disposable state; no expert decision was simulated.")


if __name__ == "__main__":
    main()
