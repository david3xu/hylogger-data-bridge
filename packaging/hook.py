# Purpose: require prebuilt UI only for release wheels, preserving clean developer setup order.
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class AssetsHook(BuildHookInterface[Any]):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name == "wheel" and version == "standard":
            ui = Path(self.root) / "app/dist"
            if not (ui / "index.html").is_file():
                raise ValueError("Build the book interface before creating a release wheel")
            build_data["force_include"][str(ui)] = "hylogger_bridge/assets/book"
