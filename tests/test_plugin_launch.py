# Purpose: prove cached plugin startup uses saved runtime settings without shell exports.
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.setup_plugin import configure


def test_cached_launcher_uses_configured_paths_and_preserves_settings(tmp_path: Path) -> None:
    repo = tmp_path / "checkout with spaces"
    python = repo / "outputs/science-env/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text(
        f"#!{sys.executable}\nimport os,json,sys\n"
        'print(json.dumps({"args":sys.argv[1:],"home":os.environ["HYLOGGER_HOME"]}))\n'
    )
    python.chmod(0o700)
    (repo / "app/dist").mkdir(parents=True)
    (repo / "app/dist/index.html").write_text("<html>UI</html>")
    data = tmp_path / "expert data"
    data.mkdir()
    config = tmp_path / "config/hylogger/runtime.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"existing_preference": "keep"}))
    cases = tmp_path / "expert books"
    configure(repo, data, cases, config)
    assert json.loads(config.read_text())["existing_preference"] == "keep"
    assert config.stat().st_mode & 0o777 == 0o600
    cached = tmp_path / "cache/hylogger/bin/hylogger-mcp"
    cached.parent.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "plugins/hylogger/bin/hylogger-mcp"
    shutil.copy2(source, cached)
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYLOGGER_")}
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    result = subprocess.run([str(cached)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    launched = json.loads(result.stdout)
    assert launched["home"] == str(repo)
    assert launched["args"][-2:] == ["--data-root", str(data)]
    assert str(cases) in launched["args"]
    # A selected model uses its own interpreter; fixture mode requires an explicit opt-out.
    model = tmp_path / "model"
    model.mkdir()
    (model / "manifest.json").write_text("{}")
    configure(repo, data, cases, config, model, Path(sys.executable))
    result = subprocess.run([str(cached)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)["args"]
    assert args[-4:] == ["--model", str(model), "--model-python", sys.executable]
    result = subprocess.run(
        [str(cached)],
        cwd=tmp_path,
        env={**env, "HYLOGGER_FIXTURE": "1"},
        capture_output=True,
        text=True,
    )
    assert "--model" not in json.loads(result.stdout)["args"]
    configure(repo, data, cases, config, fixture=True)
    assert "model" not in json.loads(config.read_text())
