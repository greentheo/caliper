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
import time
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


def too_big(parts: list, volume) -> list:
    """The pieces that still don't fit the printer. ``split`` cuts across the longest axis only, so a wide part stays wide
    (#179: the stool's 583 mm cone, on a 256 mm bed): how to section one of those is a design call, not this cut."""
    return [m for m in parts if not fits(m.extents, volume)]


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
    pieces, rest, pinned_any = [], mesh, False
    for c in cuts:
        origin = np.zeros(3)
        origin[axis] = c
        below = trimesh.intersections.slice_mesh_plane(rest, -normal, origin, cap=True)
        above = trimesh.intersections.slice_mesh_plane(rest, normal, origin, cap=True)
        pins = _pins(mesh, axis, c)
        if pins is not None:
            from .occt import OCCT

            pinned_any = True
            with OCCT:                                   # manifold3d, one boolean at a time
                below = below.difference(pins, engine="manifold")
                above = above.difference(pins, engine="manifold")
        pieces.append(below)
        rest = above
    pieces.append(rest)
    for p in pieces:
        p.metadata["pinned"] = pinned_any                # bodies simply apart have no cut, and no pins (#70 item 22)
    return pieces


def pinned(parts: list) -> bool:
    """Whether :func:`split` cut a body and put pin holes across the cut: pieces that were simply apart weren't."""
    return any(p.metadata.get("pinned") for p in parts)


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


#: Slicer results by what was sliced (the STL's bytes, material, printer size, infill, slicer): one /answers sliced each
#: piece three times, 4 s each, and that was most of a 2-minute cold open (#138 item 4).
_SLICED: dict = {}
#: CALI-104 (#97): slices started for a card that didn't wait, by the same key; their result lands in _SLICED
_PENDING: set = set()
#: a background slice that failed or timed out (#152 review), as ``(when, what to say)``: the cards take its rough
#: number, said as rough and why, and stop asking for :data:`RETRY_AFTER` (#160: one timeout on a busy machine mustn't
#: last until the server restarts); a caller that waits (the scorecard, the release) still slices again, as #140 asked
_GAVE_UP: dict = {}
#: seconds a remembered failure stands before one more background try: a slicer that always fails still starts rarely
RETRY_AFTER = 600.0
#: what a card shows while the slicer works: no number, never a stale or rough one as if final
WORKING = {"pending": True, "hours": None, "filament_g": None, "usd": None, "trust": None,
           "from": "PrusaSlicer: working it out"}
#: a slice in the background gives up sooner than one a caller waits on: a hung slicer is said, not waited on (#152).
#: Measured from when its own slicer starts, so a slice waiting behind the worker's queue loses none of it (#160).
BACKGROUND_TIMEOUT = 180.0
_QUEUE = None


def _submit(job) -> None:
    """One slicer worker for the cards: a three-piece part's slices run in turn, never three PrusaSlicers at once."""
    import queue
    import threading

    global _QUEUE
    if _QUEUE is None:
        _QUEUE = queue.Queue()

        def work():
            while True:
                fn = _QUEUE.get()
                try:
                    fn()
                except Exception:  # noqa: BLE001 — each job says its own failure; the worker keeps going
                    pass
                finally:
                    _QUEUE.task_done()

        threading.Thread(target=work, daemon=True, name="caliper-slicer").start()
    _QUEUE.put(job)


def estimate(stl_path: str, material: str, volume_mm, infill: float = M.PRINT_INFILL, wait: bool = True) -> dict:
    """Time, filament and cost for one STL: from PrusaSlicer where it's installed, else rough. Remembered by what was
    sliced, so the same piece isn't sliced again. ``wait=False`` (the cards, #97: 10 s of the bar stool's 20 s): a
    piece not sliced yet is started in the background and :data:`WORKING` comes back; the next ask has the number."""
    import hashlib

    with open(stl_path, "rb") as fh:
        key = (hashlib.sha1(fh.read()).hexdigest(), material, tuple(float(v) for v in volume_mm), float(infill),
               slicer())
    if key in _SLICED:
        return dict(_SLICED[key])
    gave_up = _GAVE_UP.get(key) if not wait else None
    if gave_up and time.monotonic() - gave_up[0] < RETRY_AFTER:
        return dict(gave_up[1])
    if not wait and slicer():
        if key not in _PENDING:
            _PENDING.add(key)
            keep = tempfile.mkdtemp(prefix="caliper-slice-")
            copy = os.path.join(keep, os.path.basename(stl_path))
            shutil.copyfile(stl_path, copy)          # the card's own file may be gone before the slicer's done

            def later():
                try:
                    got = _estimate(copy, material, volume_mm, infill, timeout=BACKGROUND_TIMEOUT)
                    if got.pop("_retry", False):         # failed or hung: the card says so (#152 review)
                        _GAVE_UP[key] = (time.monotonic(), {**got, "slicer_failed": True})
                    else:
                        _SLICED[key] = got
                        _GAVE_UP.pop(key, None)
                except Exception as e:  # noqa: BLE001 — a slice that crashed is said too, never restarted per ask
                    _GAVE_UP[key] = (time.monotonic(), {"hours": None, "filament_g": None, "usd": None, "trust": None,
                                                        "from": f"no estimate ({e})", "slicer_failed": True})
                finally:
                    _PENDING.discard(key)
                    shutil.rmtree(keep, ignore_errors=True)

            _submit(later)
        return dict(gave_up[1]) if gave_up else dict(WORKING)    # a retry shows what it had, not "working" again
    got = _estimate(stl_path, material, volume_mm, infill)
    if not got.pop("_retry", False):                  # a slicer that timed out isn't remembered (#140 review)
        _SLICED[key] = got
    return dict(got)


def _estimate(stl_path: str, material: str, volume_mm, infill: float, timeout: float = 600.0) -> dict:
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
            failed = ""
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                text = open(out, errors="ignore").read() if os.path.exists(out) else ""
            except subprocess.TimeoutExpired:
                text, failed = "", "the slicer timed out"
            except OSError as e:
                text, failed = "", f"the slicer wouldn't run ({e.strerror or e})"
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
    why = (failed if exe and failed else "the slicer gave no estimate" if exe else "no slicer installed")
    return {"hours": round(plastic / ROUGH_MM3_PER_S / 3600, 2), "filament_g": round(grams, 1),
            "usd": round(grams / 1000 * pm["usd_per_kg"], 2), "trust": "rough",
            "from": f"walls + infill at rough speeds ({why})",
            **({"_retry": True} if exe else {})}


def _hours(text: str) -> float:
    unit = {"d": 24.0, "h": 1.0, "m": 1 / 60, "s": 1 / 3600}
    return sum(float(n) * unit[u] for n, u in re.findall(r"(\d+)([dhms])", text))
