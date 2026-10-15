# Purpose: expose installed setup, diagnostics and MCP launch without repository paths.
import argparse
import importlib.metadata
import json
import os
import sys
from pathlib import Path

from hylogger_bridge.install.paths import asset, config_path, read_config


def mcp(arguments: list[str]) -> None:
    from hylogger_bridge.mcp.server import main as serve

    config = read_config()
    if not config.get("runtime_python"):
        raise ValueError("Run HyLogger setup first")
    os.environ["HYLOGGER_UI_ROOT"] = str(asset("book"))
    flags = ["--tools", "expert", "--cases", config["cases"]]
    if config.get("workspace_mode") == "host":
        from hylogger_bridge.mcp import server

        if not getattr(server, "WORKSPACE_AUTO", False):
            raise ValueError(
                "This build is waiting for the connected-workspace host adapter; "
                "installation alone does not enable workspace discovery"
            )
        flags += ["--workspace-auto"]
    elif config.get("data_root"):
        flags += ["--data-root", config["data_root"]]
    else:
        raise ValueError("Run HyLogger setup to configure the installed runtime")
    if config.get("model") and os.environ.get("HYLOGGER_FIXTURE") != "1":
        flags += ["--model", config["model"], "--model-python", config["model_python"]]
    elif os.environ.get("HYLOGGER_FIXTURE") != "1":
        raise ValueError(
            "No local model selected. Run setup with --model, or explicitly select fixture mode"
        )
    serve([*flags, *arguments])


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments and arguments[0] == "mcp":
            mcp(arguments[1:])
            return
        parser = argparse.ArgumentParser(
            description="HyLogger: install once, use your chat workspace, review evidence"
        )
        sub = parser.add_subparsers(dest="operation", required=True)
        prepare = sub.add_parser("setup", help="register the installed runtime and local plugin")
        prepare.add_argument(
            "--data-root",
            type=Path,
            help="developer override; normal setup uses the host workspace",
        )
        prepare.add_argument("--model", type=Path)
        prepare.add_argument("--model-python", type=Path)
        prepare.add_argument(
            "--no-host", action="store_true", help="prepare without changing host registration"
        )
        sub.add_parser("doctor", help="check installed resources and saved settings")
        model_check = sub.add_parser(
            "check-model", help="verify and warm the installed local model offline"
        )
        model_check.add_argument("--model", type=Path, required=True)
        model_check.add_argument("--model-python", type=Path, default=Path(sys.executable))
        args = parser.parse_args(arguments)
        if args.operation == "setup":
            from hylogger_bridge.install.setup import setup

            result = setup(args.data_root, args.model, args.model_python, not args.no_host)
            print(json.dumps(result, indent=2))
            print("HyLogger is configured. Use the folder connected to your chat host.")
        elif args.operation == "check-model":
            from hylogger_bridge.install.check import check_model

            print(json.dumps({"model_ready": check_model(args.model, args.model_python)}))
        else:
            from hylogger_bridge.mcp import server

            result = {
                "config": str(config_path()),
                "ui": str(asset("book")),
                "plugin": str(asset("plugin")),
                "science": importlib.metadata.version("pytsg"),
                "configured": bool(read_config().get("runtime_python")),
                "workspace_mode": read_config().get("workspace_mode"),
                "workspace_adapter_available": bool(getattr(server, "WORKSPACE_AUTO", False)),
                "model_selected": bool(read_config().get("model")),
            }
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError, importlib.metadata.PackageNotFoundError) as error:
        raise SystemExit(f"HyLogger: {error}") from error


if __name__ == "__main__":
    main()
