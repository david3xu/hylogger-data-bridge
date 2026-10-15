# Purpose: verify standalone review preserves expert control and separates local workspaces.
from pathlib import Path
from typing import Any

import pytest
from test_science import chips

from hylogger_bridge.advice.provider import FixtureProvider
from hylogger_bridge.cases.registry import CaseRegistry
from hylogger_bridge.install.paths import save_config
from hylogger_bridge.install.review import review


def test_review_scopes_books_and_does_not_decide(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "state"))
    save_config({"model": "test-only", "model_python": "test-only"})
    monkeypatch.setattr("hylogger_bridge.install.review.startup", lambda *a, **k: FixtureProvider())
    registries = []

    def make(cases: Path, root: Path | None, provider: Any, **kwargs: Any) -> CaseRegistry:
        reg = CaseRegistry(
            cases,
            root,
            provider,
            science=lambda *a: chips(),
            server_launcher=lambda *a: "http://127.0.0.1:12345",
            **kwargs,
        )
        registries.append(reg)
        return reg

    monkeypatch.setattr("hylogger_bridge.install.review.CaseRegistry", make)
    for name in ("first", "second"):
        root = tmp_path / name
        pkg = root / "FIX001_chips/pkg"
        pkg.mkdir(parents=True)
        (pkg / "FIX001_tsg.tsg").write_text("labelled test fixture")
        inventory = review(root, None, None, None, browser=False)
        assert inventory["packages"][0]["package_id"] == "FIX001_chips"
        started = review(root, "FIX001_chips", [5, 10], [0, 5], browser=False)
        store = registries[-1].get_store(started["case_id"])
        before = store.snapshot()
        assert len(before["pages"]) == 1 and before["pages"][0]["decision"] is None
        waited = review(root, None, None, None, case=started["case_id"], browser=False)
        assert waited["status"] == "waiting_for_decision"
        assert store.snapshot() == before
    assert registries[0].cases_dir == registries[-1].cases_dir
    assert len(list(registries[0].cases_dir.glob("*.sqlite3"))) == 2


def test_review_refuses_missing_model_and_incomplete_intervals(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with pytest.raises(ValueError, match="--target"):
        review(tmp_path, "FIX", None, None, browser=False)
    with pytest.raises(ValueError, match="local model"):
        review(tmp_path, "FIX", [5, 10], [0, 5], browser=False)
