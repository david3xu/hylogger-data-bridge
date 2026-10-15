# Purpose: the plain per-spot view of one drill-hole package, independent of any reader library.
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Hole:
    """One value per spectrum spot, in the package's own order.

    `valid` is the package's Final Mask: true for a clean core measurement. `swir` and `tir` hold
    the system interpretation's mineral group, or None where the package gave no answer.
    `identity` keeps every raw identifier found, so how `hole_id` was settled stays visible.
    """

    hole_id: str
    depth: tuple[float, ...]
    valid: tuple[bool, ...]
    swir: tuple[str | None, ...]
    tir: tuple[str | None, ...]
    files: tuple[tuple[str, str], ...]
    identity: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        sizes = {len(self.depth), len(self.valid), len(self.swir), len(self.tir)}
        if len(sizes) != 1 or not self.depth:
            raise ValueError("per-spot columns must be non-empty and of equal length")
        if not all(math.isfinite(d) for d in self.depth):
            raise ValueError("spot depths must be finite")
        if not self.hole_id.strip():
            raise ValueError("a hole needs its identifier")
