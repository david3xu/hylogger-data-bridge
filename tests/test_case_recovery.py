# Purpose: regress real case identity, interrupted initialization and authorised-folder boundaries.
import json
from pathlib import Path
from typing import Any

import pytest
from test_science import chips

from hylogger_bridge.advice.provider import FixtureProvider, Provider
from hylogger_bridge.cases.identity import case_slug, is_valid_case_id, resolve_package
from hylogger_bridge.cases.registry import CaseRegistry


def registry(root: Path, provider: Provider | None = None) -> CaseRegistry:
    (root / "data/FIX001_chips/pkg").mkdir(parents=True, exist_ok=True)
    return CaseRegistry(
        root / "cases", root / "data", provider or FixtureProvider(), science=lambda f, n: chips()
    )


def test_fractional_intervals_survive_case_tools_and_reload(tmp_path: Path) -> None:
    reg = registry(tmp_path)
    first = reg.start_case("FIX001_chips", [5.5, 9.5], [0.5, 4.5])
    assert registry(tmp_path).read_case(first["case_id"])["pages"][0]["status"] == "ready"
    assert reg.continue_case_tool(first["case_id"])["status"] == "waiting_for_decision"
    assert reg.start_case("FIX001_chips", [5.5, 9.5], [0.5, 4.5])["reused"]
    assert first["assessment"]["origin"] == "fixture"
    assert all({"source", "state", "origin"} <= e.keys() for e in first["readable_evidence"])


def test_close_but_distinct_intervals_never_alias(tmp_path: Path) -> None:
    reg = registry(tmp_path)
    a = reg.start_case("FIX001_chips", [5.000001, 9.000001], [0, 4])
    b = reg.start_case("FIX001_chips", [5.000002, 9.000002], [0, 4])
    assert a["case_id"] != b["case_id"]
    assert is_valid_case_id(case_slug("-package", [5, 10], [0, 5]))
    assert not b["reused"]
    assert case_slug("FIX001_chips", [5, 10], [0, 5]) == case_slug(
        "FIX001_chips", [5.0, 10.0], [0.0, 5.0]
    )


def test_legacy_case_is_reused_only_for_matching_criteria(tmp_path: Path) -> None:
    reg = registry(tmp_path)
    first = reg.start_case("FIX001_chips", [5.0, 9.0], [0.0, 4.0])
    old = reg.cases_dir / "fix001_chips-5_9-vs-0_4.sqlite3"
    (reg.cases_dir / f"{first['case_id']}.sqlite3").rename(old)
    again = registry(tmp_path).start_case("FIX001_chips", [5.0, 9.0], [0.0, 4.0])
    assert again["reused"] and again["case_id"] == old.stem
    different = registry(tmp_path).start_case("FIX001_chips", [5.000001, 9.000001], [0.0, 4.0])
    assert different["case_id"] != old.stem


@pytest.mark.parametrize("bad", [[float("nan"), 10], [5, float("inf")], [-1, 3], [True, 5]])
def test_invalid_bounds_create_no_book(tmp_path: Path, bad: Any) -> None:
    reg = registry(tmp_path)
    with pytest.raises(ValueError):
        reg.start_case("FIX001_chips", bad, [0, 5])
    assert not list(reg.cases_dir.glob("*.sqlite3"))


def test_interrupted_advice_resumes_with_trusted_measurements_intact(tmp_path: Path) -> None:
    class FailsOnce:
        def __init__(self) -> None:
            self.calls = 0

        def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
            self.calls += 1
            if self.calls == 1:
                raise ValueError("transient provider failure")
            return FixtureProvider().assess(request, at)

    reg = registry(tmp_path, FailsOnce())
    with pytest.raises(ValueError, match="transient"):
        reg.start_case("FIX001_chips", [5, 10], [0, 5])
    case_id = case_slug("FIX001_chips", [5, 10], [0, 5])
    evidence = reg.get_store(case_id).snapshot()["pages"][0]["evidence"]
    # Reload through a new process-like registry, rather than relying on an in-memory store.
    recovered = registry(tmp_path).start_case("FIX001_chips", [5, 10], [0, 5])
    assert recovered["reused"] and recovered["status"] == "ready"
    assert recovered["readable_evidence"][:2] == evidence
    assert registry(tmp_path).start_case("FIX001_chips", [5, 10], [0, 5])["status"] == "ready"


@pytest.mark.parametrize("location", ["parent", "nested", "file"])
def test_discovery_and_reads_refuse_outside_symlinks(tmp_path: Path, location: str) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "FIX001_tsg.tsg").write_text("outside fixture")
    data = tmp_path / "data"
    data.mkdir()
    if location == "parent":
        (data / "FIX001_chips").symlink_to(outside, target_is_directory=True)
    else:
        parent = data / "FIX001_chips"
        parent.mkdir()
        if location == "nested":
            (parent / "pkg").symlink_to(outside, target_is_directory=True)
        else:
            (parent / "FIX001_tsg.tsg").symlink_to(outside / "FIX001_tsg.tsg")
    with pytest.raises(ValueError, match="outside"):
        resolve_package(data, "FIX001_chips")
    reg = CaseRegistry(tmp_path / "cases", data, FixtureProvider())
    assert reg.find_packages_tool()["packages"] == []


def test_portable_manifests_follow_the_documented_contract() -> None:
    root = Path(__file__).resolve().parents[1] / "plugins/hylogger"
    manifest = json.loads((root / "plugin.json").read_text())
    assert manifest["$schema"].endswith("/1.0.0/plugin.schema.json")
    assert "skills" not in manifest
    mcp = json.loads((root / "mcp.json").read_text())
    assert mcp["$schema"].endswith("/1.0.0/mcp.schema.json")
    assert mcp["mcpServers"]["hylogger"]["type"] == "stdio"
    assert "${PLUGIN_ROOT}" in mcp["mcpServers"]["hylogger"]["command"]
