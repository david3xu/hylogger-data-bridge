# Purpose: recompute every record's features with a separate pandas path and compare exactly.
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytsg

NO_ANSWER = {"", "INVALID", "ASPECTRAL", "NOTAROK"}


def decode(block: Any, column: str, table: str) -> pd.Series:
    """Groups by looking the class table up by name, not through the band header link."""
    values = block.scalars[column]
    if not pd.api.types.is_numeric_dtype(values):
        text = values.astype(str).str.strip()
    else:
        names = next((c.classes for c in block.classes.values() if c.name == table), {})
        text = values.map(lambda v: names.get(int(v), "") if v > -3.0e38 else "")
    return text.where(~text.isin(NO_ANSWER), None)


def frame(folder: Path) -> pd.DataFrame:
    data = pytsg.read_tsg(str(folder))
    nir, tir = data.nir, data.tir
    return pd.DataFrame(
        {
            "depth": nir.scalars["Depth (m)"].to_numpy(),
            "valid": (nir.scalars["Final Mask"] == 1).to_numpy(),
            "swir": decode(nir, "Grp1 sTSAS", "S_SWIR_TSA705 Groups").to_numpy(),
            "tir": decode(tir, "Grp1 sjCLST", "S_jCLST_708 Groups").to_numpy(),
        }
    )


def qa(df: pd.DataFrame, top: float, bottom: float) -> dict[str, Any]:
    unique = np.unique(df["depth"].to_numpy())
    step = float(np.min(np.diff(unique))) if len(unique) > 1 else None
    rows = df[(df["depth"] >= top) & (df["depth"] < bottom)]
    clean = rows[rows["valid"]]
    expected = None if step is None else max(1, int(round((bottom - top) / step)))
    n, c = len(rows), len(clean)
    return {
        "spots": n,
        "valid": round(c / n, 4) if n else None,
        "expected": expected,
        "coverage": None
        if expected is None
        else round(min(1.0, clean["depth"].nunique() / expected), 4),
        "swir": round(clean["swir"].notna().sum() / c, 4) if c else None,
    }


def leaders(df: pd.DataFrame, top: float, bottom: float) -> tuple[pd.Series, list[str]]:
    rows = df[(df["depth"] >= top) & (df["depth"] < bottom) & df["valid"] & df["swir"].notna()]
    share = rows["swir"].value_counts(normalize=True)
    if share.empty:
        return share, []
    return share, sorted(share[share >= share.max() - 1e-9].index)


def main() -> None:
    rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
    frames: dict[str, pd.DataFrame] = {}
    bad = []
    examples = []
    for row in rows:
        hole = row["provenance"]["hole_id"]
        if hole not in frames:
            package = next(
                p for p in Path("data/raw/nvcl").glob("*/pkg") if p.parent.name.startswith(hole)
            )
            frames[hole] = frame(package)
        df = frames[hole]
        t, r = row["provenance"]["target_m"], row["provenance"]["reference_m"]
        a, b = qa(df, *t), qa(df, *r)
        got = {e["evidence_id"]: e["features"] for e in row["request"]["evidence"]}
        want: dict[str, dict[str, Any]] = {
            "inventory": {
                "target_spots": a["spots"],
                "reference_spots": b["spots"],
                "target_positions": a["expected"],
                "reference_positions": b["expected"],
            },
            "qa": {
                "target_valid": a["valid"],
                "reference_valid": b["valid"],
                "target_coverage": a["coverage"],
                "reference_coverage": b["coverage"],
                "target_swir": a["swir"],
                "reference_swir": b["swir"],
            },
        }
        sa, la = leaders(df, *t)
        sb, lb = leaders(df, *r)
        if len(sa) and len(sb):
            names = set(sa.index) | set(sb.index)
            shift = sum(abs(sa.get(g, 0.0) - sb.get(g, 0.0)) for g in names) / 2
            unique = len(la) == 1 and len(lb) == 1
            want["compare"] = {
                "group_shift": round(shift, 4),
                "lead_changed": int(la != lb) if unique else None,
                "target_leaders": len(la),
                "reference_leaders": len(lb),
            }
        else:
            want["compare"] = {
                "group_shift": None,
                "lead_changed": None,
                "target_leaders": len(la) or None,
                "reference_leaders": len(lb) or None,
            }
        for key, features in got.items():
            if features != want[key]:
                bad.append({"id": row["id"], "evidence": key, "record": features, "separate": want[key]})
        if row["meta"]["stage"] == "compare" and len(examples) < 3 and want["compare"]["lead_changed"] == 1:
            examples.append({"id": row["id"], "target": t, "reference": r, "features": got})
    report = {"records": len(rows), "holes": sorted(frames), "mismatches": bad[:5], "mismatch_count": len(bad), "examples": examples}
    Path(sys.argv[1]).with_suffix(".verify.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("records", "mismatch_count", "mismatches")}, indent=2))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
