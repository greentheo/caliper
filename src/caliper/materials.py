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
            "basis": "~1.5 lb/ft³ (Foamular 250-class); 1 in board ≈ 0.13 lb/ft²",
            # a sandwich core: stiff enough to hold the skins apart and carry shear between them
            "mech": {"E": 10.0, "G": 4.0, "strength": 0.4, "shear_strength": 0.2, "compression": 0.17,
                     "basis": "Foamular 250: compressive modulus ~1,500 psi, 25 psi compressive strength; "
                              "shear ~30 psi (rough)"},
            # cutting it (CALI-45): scored on the inside, 1 in board bends ~45° at a V-groove
            "cut": {"kerf": 3.175, "margin": 6.35, "grain": False, "fold_deg": 45.0, "score_min_deg": 5.0,
                    "note": "1 in XPS: cut with a knife or hot wire; a V-groove scored on the inside lets it "
                            "fold ~45°, and a bend under ~5° it takes without one; butt joints glued with "
                            "foam-safe adhesive, taped and glassed over"}},
    "eps": {"name": "EPS foam board", "density": 16.0, "stock": (4 * 12 * IN, 8 * 12 * IN),
            "basis": "~1 lb/ft³",
            "mech": {"E": 4.0, "G": 2.0, "strength": 0.2, "shear_strength": 0.1,
                     "basis": "1 lb/ft³ EPS (rough)"},
            "cut": {"kerf": 3.175, "margin": 6.35, "grain": False, "fold_deg": 45.0,
                    "note": "EPS: hot wire; score on the inside to fold"}},
    "plywood": {"name": "softwood plywood", "density": 560.0, "stock": (4 * 12 * IN, 8 * 12 * IN),
                "basis": "~35 lb/ft³: a 4x8 sheet of 3/8 in ≈ 35 lb, 1/2 in ≈ 47 lb",
                "mech": {"E": 8000.0, "G": 500.0, "strength": 30.0, "shear_strength": 2.0,
                         "basis": "softwood ply along its face grain (rough; across it, about half)"},
                "cut": {"kerf": 3.175, "margin": 12.7, "grain": False, "fold_deg": 0.0,
                        "note": "circular saw or CNC router; doesn't fold — every crease is a cut"}},
    # plate for gussets and brackets, plasma-cut from a sheet
    "steel": {"name": "steel plate", "density": 7850.0, "stock": (4 * 12 * IN, 8 * 12 * IN),
              "basis": "~490 lb/ft³: 3/16 in plate ≈ 7.7 lb/ft², 1/8 in ≈ 5.1 lb/ft²",
              "cut": {"kerf": 1.5, "margin": 12.7, "grain": False, "fold_deg": 0.0,
                      "note": "CNC plasma; offcuts are fine — a gusset needs no full sheet"}},
}

#: Sticks: density (kg/m³), stock length (mm), and nominal sizes -> actual section (mm).
STICKS = {
    "lumber": {"name": "SPF lumber", "density": 420.0, "stock_len": 8 * 12 * IN,
               "basis": "~26 lb/ft³ (spruce-pine-fir); a 2x2 ≈ 0.41 lb/ft",
               # construction-grade sticks with knots: break at ~2,900 psi in bending, E ~1.3 Msi
               "mech": {"E": 9000.0, "strength": 20.0,
                        "basis": "SPF #2-ish: modulus of rupture ~20 MPa with knots (clear wood ~35), E ~9 GPa"},
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
    # glass cloth wet out with epoxy (about its own weight of resin), painted over against UV
    "fiberglass": {"name": "fiberglass (1 layer 6 oz cloth + epoxy)", "areal": 0.57,
                   "basis": "6 oz/yd² E-glass (0.20 kg/m²) + as much epoxy + 2 coats of paint ≈ 0.12 lb/ft²",
                   "cloth_roll_mm": 50 * IN, "overlap": 0.10, "layers": 1, "cloth_kg_m2": 0.203,
                   "resin_ratio": 1.0, "epoxy_kg_per_gal": 4.2,
                   "paint_ft2_per_gal_coat": 350.0, "coats": 2},
    "fiberglass_2": {"name": "fiberglass (2 layers 6 oz cloth + epoxy)", "areal": 0.97,
                     "basis": "two layers of the above ≈ 0.20 lb/ft²",
                     "cloth_roll_mm": 50 * IN, "overlap": 0.10, "layers": 2, "cloth_kg_m2": 0.203,
                     "resin_ratio": 1.0, "epoxy_kg_per_gal": 4.2,
                     "paint_ft2_per_gal_coat": 350.0, "coats": 2},
}

#: How a covering works as a structural skin (CALI-44): thickness (mm), stiffness E and G (MPa) and the
#: stress it fails at (MPa). PMF has no published data — those are deliberately cautious guesses.
SKINS = {
    "pmf": {"t": 0.8, "E": 1000.0, "G": 350.0, "strength": 12.0,
            "basis": "10 oz duck tears at ~100 N/cm → ~12 MPa over ~0.8 mm with its glue; stiffness a "
                     "cautious guess (no published data)"},
    "fiberglass": {"t": 0.25, "E": 15000.0, "G": 3000.0, "strength": 200.0,
                   "basis": "woven E-glass, hand laid in epoxy: ~15 GPa, ~200 MPa (0/90 in-plane)"},
    "fiberglass_2": {"t": 0.5, "E": 15000.0, "G": 3000.0, "strength": 200.0,
                     "basis": "two layers of the above"},
    "paint": None,
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


#: What stock costs (CALI-47), USD — rough 2026 retail guesses for a cost the scorecard can compare between
#: designs, NOT quotes. Correct them for your suppliers; every cost the scorecard shows says it rests on these.
PRICES = {
    "basis": "rough retail guesses (big-box / local metal supplier), 2026 — edit materials.PRICES",
    # a whole sheet, by material and thickness (mm); plate is bought by weight
    "sheet": {("plywood", 9.525): 38.0, ("plywood", 12.7): 46.0, ("plywood", 6.35): 30.0,
              ("xps", 25.4): 42.0, ("xps", 50.8): 70.0, ("eps", 25.4): 22.0},
    "sheet_per_m2": {"plywood": 13.0, "xps": 14.0, "eps": 7.5},     # any other thickness, per 25.4 mm
    "steel_plate_per_kg": 3.3,                                        # ~$1.50/lb, small pieces
    # a whole stick of lumber; steel tube by weight
    "lumber": {"2x2": 4.5, "1x2": 3.0, "2x3": 5.0, "2x4": 6.0},
    "steel_tube_per_kg": 4.2,                                         # ~$1.90/lb
    # coverings, by what goes into them
    "canvas_per_yd": 7.0, "glass_cloth_per_yd": 9.0, "epoxy_per_gal": 110.0, "glue_per_gal": 30.0,
    "paint_per_gal": 45.0,
    "hardware_allowance": 25.0,                                       # a lump of glue, screws and hinges
}
