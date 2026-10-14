# Purpose: check local documentation links without reading private reference material.
import re
from pathlib import Path
from urllib.parse import unquote


def main() -> int:
    documents = [Path("README.md"), Path("CLAUDE.md"), Path("data/README.md")]
    documents.extend(Path("developer/docs").rglob("*.md"))
    broken: list[str] = []
    for document in documents:
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            relative = unquote(target.split("#", 1)[0])
            if not (document.parent / relative).exists():
                broken.append(f"{document}: {target}")
    for failure in broken:
        print(failure)
    if not broken:
        print("Local documentation links passed")
    return int(bool(broken))


if __name__ == "__main__":
    raise SystemExit(main())
