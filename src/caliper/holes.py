"""CALI-71 (#32) — lightening holes a part carries as data, cut after build() and counted in its pieces.

A lightening study (``lighten.py``) finds where a panel's wood isn't working and turns that into holes
cut all the way through. When one is adopted, Caliper writes them into the part's script as ``HOLES``:

    HOLES = [{"piece": "left side panel", "normal": [1, 0, 0], "depth": 19.05,
              "polygons": [[[x, y, z], ...], ...]}]

Each polygon lies on the face the piece's outline gives, and the hole goes ``depth`` along ``normal`` (into
the panel). Caliper applies them itself, so the designer's ``build()`` and ``construction()`` don't have to
know: the sandbox cuts them from whatever ``build()`` returns, and :func:`merge` gives each named piece its
``holes``, so its weight, bill of materials, consistency check and patterns all see them. Kept free of
heavy imports: the sandbox runner and the declaration probe both use it.
"""

from __future__ import annotations

NAME = "HOLES"
#: How far a cut reaches past the panel's faces, so it doesn't leave a skin from rounding.
OVERCUT = 0.5


def _newell(poly):
    nx = ny = nz = 0.0
    for i, (x0, y0, z0) in enumerate(poly):
        x1, y1, z1 = poly[(i + 1) % len(poly)]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def area(poly) -> float:
    """A flat 3D polygon's area."""
    nx, ny, nz = _newell(poly)
    return 0.5 * (nx * nx + ny * ny + nz * nz) ** 0.5


def merge(construction, holes):
    """The pieces with each named piece's ``holes`` (polygons) added; the rest as they were."""
    if not holes or not construction:
        return construction
    by = {}
    for h in holes:
        by.setdefault(h.get("piece"), []).extend(h.get("polygons") or [])
    out = []
    for item in construction:
        if isinstance(item, dict) and item.get("name") in by:
            item = {**item, "holes": [*(item.get("holes") or []), *by[item["name"]]]}
        out.append(item)
    return out


def cut(result, holes, cq):
    """``build()``'s result with every hole cut through its panel."""
    if not holes:
        return result
    shape = result.val() if hasattr(result, "val") else result
    for h in holes:
        n = [float(v) for v in h["normal"]]
        depth = float(h["depth"]) + 2 * OVERCUT
        for poly in h.get("polygons") or []:
            pts = [cq.Vector(*[float(c) - OVERCUT * nv for c, nv in zip(p, n)]) for p in poly]
            wire = cq.Wire.makePolygon(pts + [pts[0]])
            prism = cq.Solid.extrudeLinear(cq.Face.makeFromWires(wire), cq.Vector(*n) * depth)
            shape = shape.cut(prism)
    return cq.Workplane().add(shape) if hasattr(result, "val") else shape
