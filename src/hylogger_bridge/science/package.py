# Purpose: read a TSG package through pytsg into a Hole; pytsg is imported only when one is read.
import hashlib
import importlib
import re
from pathlib import Path
from typing import Any

from hylogger_bridge.science.hole import Hole

SWIR_GROUP = "Grp1 sTSAS"
TIR_GROUP = "Grp1 sjCLST"
# The package states these when no mineral group could be assigned; they are not answers.
NO_ANSWER = frozenset({"", "INVALID", "ASPECTRAL", "NOTAROK"})
# TSG writes this float32 minimum where a scalar has no value.
NO_VALUE = -3.0e38
SOURCES = ("_tsg.tsg", "_tsg.bip", "_tsg_tir.tsg", "_tsg_tir.bip")


def name_of(identifier: str) -> str:
    """The hole name inside a catalogue or file label such as KWAC018_chips."""
    return re.sub(r"[_-]?chips$", "", identifier.strip(), flags=re.IGNORECASE)


def _groups(block: Any, column: str) -> tuple[str | None, ...]:
    """Mineral groups per spot. Some packages store a class index; decode it by its class header."""
    names: dict[int, str] = {}
    for header in block.bandheaders:
        if header.name == column and header.class_number >= 0:
            names = dict(block.classes[header.class_number].classes)
    out: list[str | None] = []
    for value in block.scalars[column].tolist():
        if isinstance(value, str):
            text = value.strip()
        elif value != value or value < NO_VALUE:
            text = ""
        else:
            text = names.get(int(value), "")
        out.append(None if text in NO_ANSWER else text)
    return tuple(out)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _claims(folder: Path, nir: Any, tir: Any) -> dict[str, set[str]]:
    """Every identifier the package itself carries, by where it was found."""
    found: dict[str, set[str]] = {}
    for label, block in (("swir", nir), ("tir", tir)):
        headers = block.sampleheaders
        if "H" in headers:
            found[f"{label} sample header"] = {str(v) for v in headers["H"] if str(v).strip()}
        for table in block.classes.values():
            if table.name == "HoleID":
                found[f"{label} HoleID class"] = {str(v) for v in table.classes.values()}
    prefixes = {p.name.split("_tsg")[0] for p in folder.iterdir() if p.name.endswith("_tsg.tsg")}
    found["file names"] = prefixes
    return {label: values for label, values in found.items() if values}


Claims = dict[str, set[str]]


def identify(package_id: str, claims: Claims) -> tuple[str, tuple[tuple[str, str], ...]]:
    """The declared package identity, accepted only if nothing in the package disagrees."""
    hole = name_of(package_id)
    if not hole:
        raise ValueError("a package identifier is required")
    for label, values in claims.items():
        if len(values) != 1:
            raise ValueError(f"{label} names several holes: {sorted(values)}")
        (raw,) = values
        if name_of(raw).casefold() != hole.casefold():
            raise ValueError(f"{label} says {raw!r} but the package is declared as {package_id!r}")
    seen = tuple(sorted((label, next(iter(values))) for label, values in claims.items()))
    return hole, (("declared package", package_id), *seen)


def read(folder: Path | str, package_id: str) -> Hole:
    """Read one flat package folder; `package_id` is the catalogue name it was downloaded as."""
    path = Path(folder)
    data = importlib.import_module("pytsg").read_tsg(str(path))
    if data.nir is None or data.tir is None:
        raise ValueError(f"{path} needs both SWIR and TIR products; found {data.available}")
    nir, tir = data.nir, data.tir
    if (
        len(nir.scalars) != len(tir.scalars)
        or not (nir.scalars["Depth (m)"].to_numpy() == tir.scalars["Depth (m)"].to_numpy()).all()
    ):
        raise ValueError("SWIR and TIR spots do not line up by depth")
    hole, identity = identify(package_id, _claims(path, nir, tir))
    files = tuple((p.name, _hash(p)) for p in sorted(path.iterdir()) if p.name.endswith(SOURCES))
    return Hole(
        hole_id=hole,
        depth=tuple(float(v) for v in nir.scalars["Depth (m)"].tolist()),
        valid=tuple(bool(v == 1) for v in nir.scalars["Final Mask"].tolist()),
        swir=_groups(nir, SWIR_GROUP),
        tir=_groups(tir, TIR_GROUP),
        files=files,
        identity=identity,
    )
