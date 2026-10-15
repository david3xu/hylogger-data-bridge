# Purpose: prepare private installed settings and plugin assets while preserving expert books.
import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.assets import verify
from hylogger_bridge.install import host
from hylogger_bridge.install.paths import asset, config_path, data_home, read_config, save_config


def setup(
    data: Path | None = None,
    model: Path | None = None,
    model_python: Path | None = None,
    install_host: bool = True,
) -> dict[str, Any]:
    folder = data.expanduser().resolve() if data is not None else None
    if folder is not None and not folder.is_dir():
        raise ValueError("Choose an existing HyLogger data folder")
    # Refuse a misleading successful setup when the installed scientific reader is absent.
    importlib.metadata.version("pytsg")
    if not (asset("book") / "index.html").is_file():
        raise ValueError("The installed book interface is incomplete")
    value = read_config()
    if model_python is not None and model is None:
        raise ValueError("A model interpreter requires a model bundle")
    if model is not None:
        model = model.expanduser().resolve()
        verify(model)
        interpreter = (model_python or Path(sys.executable)).expanduser().absolute()
        if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
            raise ValueError("The selected model interpreter is unavailable")
        value.update(model=str(model), model_python=str(interpreter))
    codex = host.find_codex() if install_host else None
    root = data_home()
    version = json.loads((asset("plugin") / "plugin.json").read_text())["version"]
    plugin = root / "plugins" / version
    if not plugin.exists():
        plugin.parent.mkdir(parents=True, exist_ok=True)
        temporary = plugin.with_name(version + ".installing")
        if temporary.exists():
            shutil.rmtree(temporary)
        shutil.copytree(asset("plugin"), temporary)
        temporary.replace(plugin)
    # A fresh Mac need not have python3 on PATH. Launch the managed interpreter directly.
    for name in ("mcp.json", ".mcp.json"):
        path = plugin / name
        manifest = json.loads(path.read_text())
        manifest["mcpServers"]["hylogger"].update(
            command=str(Path(sys.executable).absolute()),
            args=["-m", "hylogger_bridge.install.cli", "mcp"],
        )
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.replace(path)
    marketplace = root / ".agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "hylogger-local",
                "plugins": [
                    {
                        "name": "hylogger",
                        "source": {"source": "local", "path": f"./plugins/{version}"},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                        "category": "Productivity",
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )
    # Keep prior cases locations, model selection and unrelated preferences intact.
    value.update(
        runtime_python=str(Path(sys.executable).absolute()),
        cases=value.get("cases", str(root / "cases")),
        workspace_mode="fixed" if folder is not None else "host",
    )
    if folder is not None:
        value["data_root"] = str(folder)
    else:
        value.pop("data_root", None)
    settings = config_path()
    previous = settings.read_bytes() if settings.exists() else None
    save_config(value)
    try:
        if codex is not None:
            host.register(root, codex)
    except BaseException:
        if previous is None:
            settings.unlink(missing_ok=True)
        else:
            settings.write_bytes(previous)
        raise
    return {
        "data_root": str(folder) if folder is not None else None,
        "workspace_mode": value["workspace_mode"],
        "cases": value["cases"],
        "plugin": str(plugin),
        "host_installed": install_host,
        "model": value.get("model"),
        "advice_mode": "model" if value.get("model") else "unconfigured",
    }
