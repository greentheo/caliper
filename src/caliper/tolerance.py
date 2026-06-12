"""CALI-19 — fits & tolerances: the vocabulary for "how snug should this be?".

A *fit* is a target band for the clearance between two mating features (or a part and a reference):
press (parts overlap, assemble with force) … running (rotates freely). Classic engineering uses ISO
grades (H7/g6) sized in microns; for FDM/printed parts the practical clearances are roughly *absolute*
(~0.2 mm), not proportional, so we define printer-friendly bands by default. A fit class expands to a
concrete ``(lo, hi)`` clearance band, which becomes a two-sided assertion the optimizer can tune into
(the evaluator now reports a signed margin for ``lo <= x <= hi`` — distance to the nearest bound).

Also home to the tolerance helpers bound into the evaluator namespace (``approx``, ``within``,
``fits``) so specs can express "near a value, within measurement noise" instead of brittle ``==`` or a
hard threshold that loses to a 0.01 mm ray-cast wobble.
"""

from __future__ import annotations

from typing import Optional

# Clearance bands in mm (gap between the part and what it mates to). Negative = interference (overlap).
# Tuned for FDM: a typical printed clearance that "just slides" is ~0.2 mm regardless of size.
FIT_CLASSES: dict[str, tuple[float, float]] = {
    "press":   (-0.12, 0.00),   # interference — assemble with force / a press
    "snug":    (0.00, 0.12),    # transition — light tap, no play
    "slip":    (0.12, 0.30),    # clearance — slides together, no slop  (the sensible default)
    "free":    (0.30, 0.60),    # easy hand assembly, a little play
    "running": (0.45, 0.90),    # rotates / slides freely
}
# friendly synonyms → canonical class
FIT_ALIASES: dict[str, str] = {
    "interference": "press", "force": "press",
    "transition": "snug", "tight": "snug",
    "clearance": "slip", "sliding": "slip", "location": "slip",
    "loose": "free", "clearance_loose": "free", "easy": "free",
    "rotating": "running", "rotation": "running", "spin": "running",
}

DEFAULT_FIT = "slip"


def fit_band(kind: str, nominal: Optional[float] = None) -> tuple[float, float]:
    """Resolve a fit-class name (or synonym) to a ``(lo, hi)`` clearance band in mm.

    ``nominal`` (the mating size) is accepted for future ISO-style size scaling; FDM bands are treated
    as absolute for now, so it's currently only widened very slightly for large parts (> 50 mm).
    """
    key = (kind or DEFAULT_FIT).strip().lower()
    key = FIT_ALIASES.get(key, key)
    if key not in FIT_CLASSES:
        raise ValueError(f"unknown fit class {kind!r}; choose from {', '.join(FIT_CLASSES)} "
                         f"(or {', '.join(FIT_ALIASES)})")
    lo, hi = FIT_CLASSES[key]
    if nominal and nominal > 50:  # gentle widening for big mating sizes (printed parts grow tolerance)
        extra = round(0.05 * (nominal - 50) / 50.0, 3)
        lo, hi = (lo if lo < 0 else lo, hi + extra)
    return float(lo), float(hi)


def fit_classes() -> list[str]:
    return list(FIT_CLASSES)


# ---------------------------------------------------------------------------
# evaluator helpers (bound into the assertion namespace) — tolerant comparisons
# ---------------------------------------------------------------------------
def approx(actual: float, nominal: float, tol: float = 0.1) -> bool:
    """True if ``actual`` is within ``±tol`` of ``nominal`` — absorbs measurement noise / round-off."""
    return abs(float(actual) - float(nominal)) <= float(tol)


def within(actual: float, lo: float, hi: float) -> bool:
    """True if ``lo <= actual <= hi`` (a tolerance band as a function call)."""
    return float(lo) <= float(actual) <= float(hi)


def fits(clearance: float, kind: str = DEFAULT_FIT, nominal: Optional[float] = None) -> bool:
    """True if a measured ``clearance`` (mm) lands in the band for fit class ``kind``."""
    lo, hi = fit_band(kind, nominal)
    return lo <= float(clearance) <= hi
