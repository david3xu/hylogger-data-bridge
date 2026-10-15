# Purpose: download the frozen NVCL hole packages (CC BY 4.0) into ignored data/raw/, with hashes.
import argparse
import hashlib
import json
import shutil
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://thredds.nci.org.au/thredds/fileServer/rs07/WA/"
LICENCE = "https://thredds.nci.org.au/thredds/fileServer/rs07/license/license_CCBY4.txt"


def fetch(name: str, root: Path) -> dict[str, str | int]:
    """One zip, once: its URL, retrieval time, size and SHA-256 go to retrieval.jsonl."""
    url = BASE + urllib.parse.quote(name)
    target = root / name
    request = urllib.request.Request(url, headers={"User-Agent": "hylogger-r1"})
    with urllib.request.urlopen(request, timeout=300) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out)
    entry: dict[str, str | int] = {
        "url": url,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "licence": LICENCE,
        "file": name,
    }
    with (root / "retrieval.jsonl").open("a") as log:
        log.write(json.dumps(entry) + "\n")
    return entry


def flatten(archive: Path, folder: Path) -> None:
    """Package zips store Windows-style names; keep only each file's own name."""
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        for info in zipped.infolist():
            if not info.is_dir():
                base = info.filename.replace("\\", "/").split("/")[-1]
                with zipped.open(info) as source, (folder / base).open("wb") as out:
                    shutil.copyfileobj(source, out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("training/real.json"))
    parser.add_argument("--only", nargs="*", help="package names, instead of every frozen one")
    args = parser.parse_args()
    plan = json.loads(args.config.read_text())
    root = Path(plan["root"])
    root.mkdir(parents=True, exist_ok=True)
    for name in args.only or plan["packages"]:
        archive = root / name
        if not archive.exists():
            print("downloaded", fetch(name, root)["sha256"], name)
        flatten(archive, root / name.removesuffix(".zip") / "pkg")


if __name__ == "__main__":
    main()
