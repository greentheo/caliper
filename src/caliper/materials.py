"""CALI-41 — what things are made of: densities, stock sizes, and the rates a bill of materials needs.

Shared by every part that declares how it's built (:mod:`caliper.construction`). SI inside (kg, mm);
the page shows pounds and inches. Densities are typical values for what a hardware store sells, with the
basis noted so they can be corrected — a design's weight is only as good as these numbers.
"""

from __future__ import annotations

IN = 25.4
FT2_MM2 = (12 * IN) ** 2
LB_KG = 2.20462262

#: Sheet goods: density (kg/m³) and the stock sheet (mm).
SHEETS = {
    "xps": {"name": "XPS foam board", "density": 24.0, "stock": (4 * 12 * IN, 8 * 12 * IN),
            "basis": "~1.5 lb/ft³ (Foamular 250-class); 1 in board ≈ 0.13 lb/ft²"},
    "eps": {"name": "EPS foam board", "density": 16.0, "stock": (4 * 12 * IN, 8 * 12 * IN),
            "basis": "~1 lb/ft³"},
    "plywood": {"name": "softwood plywood", "density": 560.0, "stock": (4 * 12 * IN, 8 * 12 * IN),
                "basis": "~35 lb/ft³: a 4x8 sheet of 3/8 in ≈ 35 lb, 1/2 in ≈ 47 lb"},
    # plate for gussets and brackets, plasma-cut from a sheet
    "steel": {"name": "steel plate", "density": 7850.0, "stock": (4 * 12 * IN, 8 * 12 * IN),
              "basis": "~490 lb/ft³: 3/16 in plate ≈ 7.7 lb/ft², 1/8 in ≈ 5.1 lb/ft²"},
}

#: Sticks: density (kg/m³), stock length (mm), and nominal sizes -> actual section (mm).
STICKS = {
    "lumber": {"name": "SPF lumber", "density": 420.0, "stock_len": 8 * 12 * IN,
               "basis": "~26 lb/ft³ (spruce-pine-fir); a 2x2 ≈ 0.41 lb/ft",
               "sizes": {"2x2": (1.5 * IN, 1.5 * IN), "1x2": (0.75 * IN, 1.5 * IN),
                         "2x3": (1.5 * IN, 2.5 * IN), "2x4": (1.5 * IN, 3.5 * IN)}},
    # square tube is sized by its outside and wall, not by name (construction.tube_area)
    "steel": {"name": "steel tube", "density": 7850.0, "stock_len": 20 * 12 * IN,
              "basis": "~490 lb/ft³; sold in 20 ft or 24 ft sticks", "sizes": {}},
}

#: Coverings: areal density (kg/m²) and what goes into them, for the bill of materials.
COVERINGS = {
    "pmf": {"name": "poor man's fiberglass", "areal": 0.88,
            "basis": "canvas (10 oz duck, ~0.07 lb/ft²) + glue (~0.05) + 2-3 coats of exterior paint "
                     "(~0.05) ≈ 0.18 lb/ft² dried",
            "canvas_roll_mm": 60 * IN, "overlap": 0.10,
            "glue_ft2_per_gal": 100.0, "paint_ft2_per_gal_coat": 350.0, "coats": 3},
    "paint": {"name": "exterior paint (sealer)", "areal": 0.24,
              "basis": "2-3 coats of exterior latex ≈ 0.05 lb/ft² dried",
              "paint_ft2_per_gal_coat": 350.0, "coats": 3},
}


def sheet(material: str) -> dict:
    if material not in SHEETS:
        raise ValueError(f"unknown sheet material {material!r} — known: {', '.join(SHEETS)}")
    return SHEETS[material]


def stick(material: str, size: str) -> tuple[dict, tuple[float, float]]:
    if material not in STICKS:
        raise ValueError(f"unknown stick material {material!r} — known: {', '.join(STICKS)}")
    m = STICKS[material]
    if size not in m["sizes"]:
        raise ValueError(f"no {size!r} {material} — known: {', '.join(m['sizes'])}")
    return m, m["sizes"][size]


def covering(material: str) -> dict:
    if material not in COVERINGS:
        raise ValueError(f"unknown covering {material!r} — known: {', '.join(COVERINGS)}")
    return COVERINGS[material]


def nominal(thickness_mm: float) -> str:
    """A thickness the way a lumber yard says it: 9.525 mm -> '3/8 in'."""
    eighths = round(thickness_mm / IN * 16)
    whole, rest = divmod(eighths, 16)
    if rest == 0:
        return f"{whole} in"
    from math import gcd

    g = gcd(rest, 16)
    frac = f"{rest // g}/{16 // g}"
    return f"{whole} {frac} in" if whole else f"{frac} in"
