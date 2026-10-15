# Purpose: stdio smoke test for MCP server, expert tools, case reuse, and real package reading.
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any


def main() -> None:
    cases_dir = Path("outputs/cases")
    cases_dir.mkdir(parents=True, exist_ok=True)
    # Clean up any previous test case file for SWMB007s
    case_slug = "swmb007s_chips-5_10-vs-0_5"
    (cases_dir / f"{case_slug}.sqlite3").unlink(missing_ok=True)
    (cases_dir / f"{case_slug}.server.json").unlink(missing_ok=True)

    python_bin = "outputs/science-env/bin/python"
    if not Path(python_bin).exists():
        python_bin = sys.executable

    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."

    cmd = [
        python_bin,
        "-m",
        "hylogger_bridge.mcp.server",
        "--cases",
        "outputs/cases",
        "--data-root",
        "data/raw/nvcl",
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stdin = proc.stdin
    stdout = proc.stdout
    assert stdin is not None
    assert stdout is not None

    def ask(msg_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        req = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
        stdin.write(json.dumps(req) + "\n")
        stdin.flush()
        line = stdout.readline()
        if not line:
            stderr_out = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Server closed connection unexpectedly. Stderr: {stderr_out}")
        parsed: dict[str, Any] = json.loads(line)
        return parsed

    def tool(msg_id: int, name: str, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        reply = ask(msg_id, "tools/call", {"name": name, "arguments": arguments})
        res = reply["result"]
        content: dict[str, Any] = json.loads(res["content"][0]["text"])
        return res["isError"], content

    results: dict[str, str] = {}

    # 1. initialize
    init_res = ask(1, "initialize")
    assert "capabilities" in init_res["result"], f"Init failed: {init_res}"

    # 2. tools/list
    list_res = ask(2, "tools/list")
    tools = [t["name"] for t in list_res["result"]["tools"]]
    assert "start_case" in tools
    assert "read_case" in tools
    assert "continue_case" in tools
    assert "open_book" in tools
    assert "find_packages" in tools
    assert "list_cases" in tools
    results["tools/list"] = f"{len(tools)} tools declared ({', '.join(tools[:6])}...)"

    # 3. find_packages
    err, pkgs = tool(3, "find_packages", {"hole": "SWMB007s"})
    assert not err
    results["find_packages"] = (
        f"found {len(pkgs['packages'])} package(s): {pkgs['packages'][0]['package_id']}"
    )

    # 4. list_cases (before start)
    err, initial_cases = tool(4, "list_cases", {})
    assert not err
    results["list_cases"] = f"{len(initial_cases['cases'])} active case(s)"

    # 5. start_case (first call -> fresh)
    err, start1 = tool(
        5,
        "start_case",
        {"package_id": "SWMB007s_chips", "target": [5.0, 10.0], "reference": [0.0, 5.0]},
    )
    assert not err
    case_id = start1["case_id"]
    assert start1["reused"] is False
    assert start1["advice_origin"] == "fixture"
    evidence_labels = [e["label"] for e in start1["readable_evidence"]]
    results["start_case"] = (
        f"case_id={case_id}, reused={start1['reused']}, origin={start1['advice_origin']}, "
        f"evidence={evidence_labels}"
    )

    # 6. start_case (second call -> reused)
    err, start2 = tool(
        6,
        "start_case",
        {"package_id": "SWMB007s_chips", "target": [5.0, 10.0], "reference": [0.0, 5.0]},
    )
    assert not err
    assert start2["case_id"] == case_id
    assert start2["reused"] is True
    results["start_case (reused)"] = f"case_id={case_id}, reused={start2['reused']}"

    # 7. open_book twice
    err, open1 = tool(7, "open_book", {"case_id": case_id})
    assert not err
    url1 = open1["url"]

    err, open2 = tool(8, "open_book", {"case_id": case_id})
    assert not err
    url2 = open2["url"]
    assert url1 == url2, f"Expected same URL, got {url1} vs {url2}"
    results["open_book"] = f"URL={url1} (reused on second call)"

    # 8. read_case
    err, read_res = tool(9, "read_case", {"case_id": case_id})
    assert not err
    assert read_res["human_decision_pending"] is False
    assert len(read_res["pages"]) == 1
    results["read_case"] = (
        f"pages={len(read_res['pages'])}, status={read_res['pages'][0]['status']}, "
        f"human_decision_pending={read_res['human_decision_pending']}"
    )

    # 9. continue_case (with no decision pending)
    err, cont_res = tool(10, "continue_case", {"case_id": case_id})
    assert not err
    assert cont_res["status"] == "waiting_for_decision"
    results["continue_case"] = f"status={cont_res['status']} ({cont_res['message'][:40]}...)"

    # Clean up book server process
    server_file = cases_dir / f"{case_id}.server.json"
    if server_file.exists():
        try:
            s_data = json.loads(server_file.read_text())
            os.kill(int(s_data["pid"]), signal.SIGTERM)
        except OSError:
            pass
        server_file.unlink(missing_ok=True)

    # Terminate MCP server process
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()

    print("\n--- SMOKE TEST RESULTS ---")
    for tool_name, summary in results.items():
        print(f"  {tool_name}: {summary}")
    print("--------------------------\n")
    print("Smoke test passed successfully!")


if __name__ == "__main__":
    main()
