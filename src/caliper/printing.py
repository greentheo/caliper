"""CALI-48 (#4) — a printed part, made to fit your printer: split where it has to be, and what it costs.

A part that says it's printed (``{"kind": "printed", "material": "petg"}`` in its ``construction()``) gets
its STL ready for the printer in the shop:

- **It fits, or it's split.** It's turned onto whichever axis it fits if that's enough. If not, it's cut
  into pieces that fit, square across its longest side. Each cut face gets pin holes (3 mm, 10 mm deep each
  side) for short lengths of filament or 1/8 in dowel, so the halves line up and glue square.
- **What it costs:** PrusaSlicer's command line, where it's installed, slices each piece for the printer's
  volume and says the time and the filament. Without it the estimate is the walls plus 20% infill, at
  rough speeds, and says it's rough.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional

import numpy as np

from . import materials as M

#: The pins: holes this wide and this deep each side of a cut, kept this far from its edges.
PIN_D_MM, PIN_DEPTH_MM, PIN_EDGE_MM = 3.2, 10.0, 6.0
FILAMENT_D_MM = 1.75
#: Without a slicer: a printer lays down about this much plastic a second, all in.
ROUGH_MM3_PER_S = 6.0
#: Clearance inside the build volume.
BED_MARGIN_MM = 5.0


def slicer() -> Optional[str]:
    """PrusaSlicer's command line, if it's here (``CALIPER_SLICER`` names another, or "" for none)."""
    if os.environ.get("CALIPER_SLICER") == "":
        return None
    for p in (os.environ.get("CALIPER_SLICER"), shutil.which("prusa-slicer"), shutil.which("PrusaSlicer"),
              "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"):
        if p and os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return None


def fits(extents, volume) -> bool:
    """Fits the build volume in some axis-aligned orientation."""
    room = sorted(float(v) - BED_MARGIN_MM for v in volume)
    return all(a <= b for a, b in zip(sorted(float(e) for e in extents), room))


def split(mesh, volume) -> list:
    """The part as pieces that each fit the printer, with pin holes across every cut."""
    import trimesh

    if fits(mesh.extents, volume):
        return [mesh]
    axis = int(np.argmax(mesh.extents))
    longest = sorted(float(v) - BED_MARGIN_MM for v in volume)[-1]
    n = max(2, math.ceil(float(mesh.extents[axis]) / longest))
    lo, hi = float(mesh.bounds[0][axis]), float(mesh.bounds[1][axis])
    cuts = [lo + (hi - lo) * k / n for k in range(1, n)]
    normal = np.zeros(3)
    normal[axis] = 1.0
    pieces, rest = [], mesh
    for c in cuts:
        origin = np.zeros(3)
        origin[axis] = c
        below = trimesh.intersections.slice_mesh_plane(rest, -normal, origin, cap=True)
        above = trimesh.intersections.slice_mesh_plane(rest, normal, origin, cap=True)
        pins = _pins(mesh, axis, c)
        if pins is not None:
            from .occt import OCCT

            with OCCT:                                   # manifold3d, one boolean at a time
                below = below.difference(pins, engine="manifold")
                above = above.difference(pins, engine="manifold")
        pieces.append(below)
        rest = above
    pieces.append(rest)
    return pieces


def _pins(mesh, axis: int, at: float):
    """Pin holes straddling a cut: up to three, inside the cross-section, clear of its edges."""
    import trimesh
    from shapely.geometry import Polygon

    origin, normal = np.zeros(3), np.zeros(3)
    origin[axis], normal[axis] = at, 1.0
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        return None
    flat, to3d = sec.to_2D()
    area = flat.polygons_full
    if not area:
        return None
    region = max(area, key=lambda p: p.area).buffer(-(PIN_EDGE_MM + PIN_D_MM / 2))
    if region.is_empty:
        return None
    region = max(getattr(region, "geoms", [region]), key=lambda p: p.area)
    pts = [region.representative_point()]
    for corner in Polygon(region.envelope).exterior.coords[:4]:
        # towards each corner of the section: spread pins stop it twisting
        q = region.exterior.interpolate(region.exterior.project(type(pts[0])(corner)))
        c = pts[0]
        cand = type(c)(c.x + 0.7 * (q.x - c.x), c.y + 0.7 * (q.y - c.y))
        if region.contains(cand) and all(cand.distance(p) > 4 * PIN_D_MM for p in pts):
            pts.append(cand)
        if len(pts) == 3:
            break
    holes = []
    for p in pts:
        cyl = trimesh.creation.cylinder(radius=PIN_D_MM / 2, height=2 * PIN_DEPTH_MM, sections=24)
        cyl.apply_translation([p.x, p.y, 0.0])
        cyl.apply_transform(to3d)
        holes.append(cyl)
    return trimesh.util.concatenate(holes)


def estimate(stl_path: str, material: str, volume_mm, infill: float = M.PRINT_INFILL) -> dict:
    """Time, filament and cost for one STL: from PrusaSlicer where it's installed, else rough."""
    pm = M.printed(material)
    density = pm["density"] / 1000.0                        # g/cm³
    exe = slicer()
    if exe:
        x, y, z = (float(v) for v in volume_mm)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "part.gcode")
            cmd = [exe, "--export-gcode", "--output", out, "--bed-shape", f"0x0,{x:g}x0,{x:g}x{y:g},0x{y:g}",
                   "--max-print-height", f"{z:g}", "--center", f"{x / 2:g},{y / 2:g}",
                   "--fill-density", f"{round(infill * 100)}%", "--filament-density", f"{density:g}",
                   "--filament-diameter", f"{FILAMENT_D_MM:g}", stl_path]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                text = open(out, errors="ignore").read() if os.path.exists(out) else ""
            except (subprocess.TimeoutExpired, OSError):
                text = ""
        t = re.search(r"estimated printing time \(normal mode\) = ([^\n]+)", text)
        mm = re.search(r"filament used \[mm\] = ([\d.]+)", text)
        if t and mm:
            grams = float(mm.group(1)) * math.pi * (FILAMENT_D_MM / 2) ** 2 / 1000 * density
            return {"hours": round(_hours(t.group(1)), 2), "filament_g": round(grams, 1),
                    "usd": round(grams / 1000 * pm["usd_per_kg"], 2), "trust": "model",
                    "from": "PrusaSlicer, default profile at this printer's size"}
    import trimesh

    m = trimesh.load(stl_path, force="mesh")
    vol, area = float(abs(m.volume)), float(m.area)
    shell = min(vol, area * M.PRINT_SHELL_MM)
    plastic = shell + infill * (vol - shell)
    grams = plastic / 1000 * density
    return {"hours": round(plastic / ROUGH_MM3_PER_S / 3600, 2), "filament_g": round(grams, 1),
            "usd": round(grams / 1000 * pm["usd_per_kg"], 2), "trust": "rough",
            "from": "walls + infill at rough speeds (no slicer installed)"}


def _hours(text: str) -> float:
    unit = {"d": 24.0, "h": 1.0, "m": 1 / 60, "s": 1 / 3600}
    return sum(float(n) * unit[u] for n, u in re.findall(r"(\d+)([dhms])", text))
