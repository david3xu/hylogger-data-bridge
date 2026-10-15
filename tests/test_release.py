# Purpose: ensure public model metadata excludes reference measurements and machine details.
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def test_public_manifest_omits_reference_records(tmp_path: Path, monkeypatch: Any) -> None:
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("release_product", scripts / "release_product.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_product"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "verify", lambda folder: {})
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "version": "test",
                "files": {},
                "reference": [{"measurement": 1}],
                "python": "private machine",
                "host": "private",
                "source_files": [],
            }
        )
    )
    module.public_manifest(tmp_path)
    value = json.loads(path.read_text())
    assert value["version"] == "test" and value["files"] == {}
    assert not {"reference", "python", "host", "source_files"} & value.keys()
