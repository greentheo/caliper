"""CALI-54 (#1) — will it hold? What a part says it must carry, checked two ways.

A part says what it must hold in ``loads()`` (an adult stepping up, a shelf of books) and where it's
held in ``held()`` (the floor, when it doesn't say). Caliper checks it two ways and goes by the worse:

- **whittle's voxel FEA** of the part as built, in the material its ``construction()`` names: a stress
  picture (where it works hardest), how far it gives, and a peak *beside* where the load and the floor
  attach (right at a contact, a voxel model reports the mesh, not the part). With about four voxels
  through a 3/4 in panel it's good for the picture and to perhaps ±50% on the number: the joints are
  solid wood to it, and a panel's edges come out partly clamped.
- **A plate check** for a sheet a load pushes on face-on and that rests on other pieces all round: the
  panel as a flat plate free to rotate at its edges (simply supported, the safe side of glued and
  screwed) with the load over its footprint at the middle, the worst place (Roark, Table 11.4).
  Plywood is about half as strong across its face grain, so it's said both ways, and the verdict
  takes the grain the wrong way.

The verdict is the lower safety factor at the load times its ``factor`` (2 for someone stepping onto
it), against ``min_safety``. Neither model checks the glue or the screws.
"""

from __future__ import annotations

import base64
import json
import math
import os
import time
import uuid
from typing import Callable, Optional

import numpy as np

from . import construction as C
from . import materials as M
from . import verdicts as V
from .design import DesignStore
from .one_study import one_at_a_time
from .runs import newest_first

LB = 4.4482216152605          # newtons per pound-force
GRAVITY = 9.80665
#: Voxels through the thinnest piece, if the part isn't so big that it would take too long.
VOXELS_THROUGH = 4
MAX_VOXELS = 150_000
MIN_SAFETY = 2.0
POISSON = 0.3
#: Roark Table 11.4, a rectangular plate simply supported on all edges, ν = 0.3, by a/b (long/short):
#: β for the stress under a load on a small central circle, α for the deflection there.
_AB = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 1e9]
_BETA = [0.435, 0.650, 0.789, 0.875, 0.927, 0.958, 1.000]
_ALPHA = [0.1267, 0.1478, 0.1621, 0.1714, 0.1769, 0.1803, 0.1851]
#: whittle's own figures, for a material Caliper's table has no mechanical properties for.
_WHITTLE_NAMES = {"steel": "steel", "plywood": "plywood", "xps": "xps", "aluminum": "aluminum"}


# ---------------------------------------------------------------------------
# What the part declares
# ---------------------------------------------------------------------------
def _box(item: dict, what: str) -> tuple[list[float], list[float]]:
    try:
        lo = [float(v) for v in item["lo"]]
        hi = [float(v) for v in item["hi"]]
    except KeyError as e:
        raise ValueError(f"{what} needs {e.args[0]!r}: the corners of the box it acts on") from None
    except (TypeError, ValueError):
        raise ValueError(f"{what}: lo and hi are (x, y, z) in mm") from None
    if len(lo) != 3 or len(hi) != 3:
        raise ValueError(f"{what}: lo and hi are (x, y, z) in mm")
    return [min(a, b) for a, b in zip(lo, hi)], [max(a, b) for a, b in zip(lo, hi)]


def parse_loads(items) -> list[dict]:
    """``loads()`` as Caliper uses it: name, the force (N, as declared) and factor, the box it acts on.
    Raises ValueError, naming the load, for anything it can't act on."""
    if not isinstance(items, (list, tuple)):
        raise ValueError("loads() returns a list of loads")
    out = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"load {i + 1} isn't a dict")
        name = str(item.get("name") or f"load {i + 1}")
        lo, hi = _box(item, f"'{name}'")
        if "force" in item:
            force = [float(v) for v in item["force"]]
            if len(force) != 3:
                raise ValueError(f"'{name}': force is (fx, fy, fz) in newtons")
        elif "lb" in item:
            force = [0.0, 0.0, -float(item["lb"]) * LB]
        elif "kg" in item:
            force = [0.0, 0.0, -float(item["kg"]) * GRAVITY]
        else:
            raise ValueError(f"'{name}' says where but not how much: give lb, kg or force")
        factor = float(item.get("factor", 1.0))
        if factor <= 0 or not math.isfinite(factor) or not any(force):
            raise ValueError(f"'{name}': the load and its factor must be more than nothing")
        out.append({"name": name, "force": force, "factor": factor, "lo": lo, "hi": hi,
                    "lb": round(float(np.linalg.norm(force)) / LB, 1)})
    return out


def parse_held(items, bounds, depth: float) -> list[dict]:
    """``held()``, or the floor: everything within ``depth`` of the part's underside."""
    if not items:
        (x0, y0, z0), (x1, y1, _) = bounds
        return [{"name": "the floor", "lo": [x0 - 1, y0 - 1, z0 - 1], "hi": [x1 + 1, y1 + 1, z0 + depth],
                 "default": True}]
    out = []
    for i, item in enumerate(items):
        name = str(item.get("name") or f"support {i + 1}")
        lo, hi = _box(item, f"'{name}'")
        out.append({"name": name, "lo": lo, "hi": hi})
    return out


def material(pieces: list[dict]) -> dict:
    """The one material the part is analysed in: what most of it is made of, by volume."""
    by = {}
    for pc in pieces:
        by[pc["material"]] = by.get(pc["material"], 0.0) + pc["volume"]
    if not by:
        raise ValueError("it doesn't say what it's built from (construction()), so there's no "
                         "material to analyse it in")
    key = max(by, key=by.get)
    table = M.SHEETS.get(key) or M.STICKS.get(key) or {}
    mech = table.get("mech")
    if mech:
        out = {"key": key, "name": table["name"], "E": mech["E"], "strength": mech["strength"],
               "density": table["density"] / 1000.0, "basis": mech.get("basis", "")}
    else:
        from whittle import MATERIALS

        w = MATERIALS.get(_WHITTLE_NAMES.get(key, key))
        if w is None:
            raise ValueError(f"the materials table has no strength for {key!r}")
        out = {"key": key, "name": table.get("name", w.name), "E": w.youngs_modulus,
               "strength": w.strength, "density": w.density, "basis": f"whittle's {w.name}"}
    # plywood is about half as strong across its face grain (see the materials table's basis)
    out["across"] = 0.5 if key == "plywood" else 1.0
    if len(by) > 1:
        out["note"] = (f"Analysed as all {out['name']} (most of it by volume); it's also "
                       + ", ".join(k for k in by if k != key) + ".")
    return out


#: A print across its layers is about half as strong as along them (the layers' bond), and which way a wall is
#: pulled isn't known: so a printed part is taken at the weaker.
LAYERS_ACROSS = 0.5


def printed_material(declared: dict, mesh, printed_mesh=None) -> Optional[dict]:
    """CALI-81: a part printed whole, analysed as a solid of its plastic at the share of it that's plastic (its
    perimeters and infill) and at half strength for its layers. Rough, on the safe side, until a printed test
    piece says otherwise (#42). None if it isn't printed."""
    it = next((x for x in declared.get("construction") or [] if isinstance(x, dict) and x.get("kind") == "printed"),
              None)
    if it is None:
        return None
    from whittle import MATERIALS

    key = it.get("material", "pla")
    w, pm = MATERIALS.get(key), M.printed(key)
    if w is None:
        raise ValueError(f"the materials table has no strength for printed {key!r}")
    body = printed_mesh if printed_mesh is not None else mesh      # a printed rest: just the printed solid
    vol, area = float(abs(body.volume)), float(body.area)
    shell = min(vol, area * M.PRINT_SHELL_MM)
    infill = float(it.get("infill", M.PRINT_INFILL))
    solid = (shell + infill * (vol - shell)) / vol if vol else 1.0
    return {"key": key, "name": pm["name"], "E": w.youngs_modulus * solid,
            "strength": w.strength * solid * LAYERS_ACROSS, "density": pm["density"] / 1000.0 * solid,
            "across": 1.0, "printed": True, "solid": round(solid, 3),
            "basis": f"whittle's {w.name} (E {w.youngs_modulus:g} MPa, strength {w.strength:g} MPa) at {solid:.0%}, "
                     f"the share that's plastic ({M.PRINT_SHELL_MM:g} mm walls, {infill:.0%} infill), and half that "
                     f"strength across its layers",
            "note": "Printed: a rough model on the safe side. Infill and the bond between layers vary from printer "
                    "to printer; a printed test piece loaded to breaking is the way to know."}


def finest(volume: float, longest: float, budget: float = 1.0) -> float:
    """The finest voxels a study may use on a part this size: no more than MAX_VOXELS in it and 160 along it, each
    times ``budget`` (in voxels, so 8 is twice as fine). Nothing, an asked-for size included, goes finer (CALI-97)."""
    return max((volume / (MAX_VOXELS * budget)) ** (1 / 3), longest / (160 * budget ** (1 / 3)))


def spacing_for(pieces: list[dict], volume: float, longest: float, walls: Optional[float] = None) -> tuple[float, Optional[str]]:
    """Voxel size: VOXELS_THROUGH across the thinnest piece (or, printed, its walls), unless that's more voxels
    than a study should take; then as fine as MAX_VOXELS allows, and a note saying so."""
    thin = [pc["thickness"] for pc in pieces if pc["kind"] == "sheet"]
    thin += [2 * pc["half"] for pc in pieces if pc["kind"] == "stick"]
    if walls and walls > 0:
        thin.append(walls)
    want = min(thin) / VOXELS_THROUGH if thin else longest / 48
    floor = finest(volume, longest)
    if want >= floor:
        return want, None
    return floor, (f"The voxels are {floor:.1f} mm, coarser than {VOXELS_THROUGH} across its thinnest "
                   f"piece ({min(thin):.1f} mm), to keep the study quick: read the FEA as a picture.")


#: Voxels the FEA needs across the thinnest wall before its number can carry a verdict (CALI-97). NEEDS ENGINEER
#: CHECK: 4 until #42's convergence study sets it from data. At 2, the printed box read ✓ 2.7x, and ✗ 1.9x at 4: a
#: ✓ that a finer check overturns (the foreman's call on #100, the safe side).
RESOLVE_MIN = 4.0
#: A finer run, offered when the default's voxels can't see a wall, may use this many times the default's voxel
#: budget and no more (8: twice as fine each way), so no click asks for 10^10 voxels on a shared machine.
FINER_BUDGET = 8.0
#: The verdict where even the finest run a study may make can't see the walls.
NOT_CHECKED = ("Not checked: its walls are too thin for the voxel check at this size. A hand check or a printed "
               "test piece is the way to know.")


def _thin(declared: dict, mesh, pieces: list[dict]) -> tuple[list, Optional[float], dict, list]:
    """Every piece's thinnest dimension, and a printed part's thinnest wall (measured). The thinnest, not a
    percentile: a thin neck the load goes through is a sliver of the surface, and a percentile let 5 mm voxels
    "see" a spool hung from a 0.6 mm neck and call it ✓ (#100, the reviewer's spool; rule 6). Where the thinnest
    spot is only a lip, the cap says "not checked", the safe side. And where the thinnest is: ``{"piece": name}``,
    or ``{"at": (x, y, z)}`` for a measured wall, so a line can say where to thicken it (#136 review). And every wall, as
    ``(mm, where)``, for :func:`unseen_walls` (#248 review)."""
    walls, at = None, None
    if any(isinstance(it, dict) and it.get("kind") == "printed" for it in declared.get("construction") or []):
        from .measure import Geometry, thinnest_wall

        walls, at = thinnest_wall(Geometry.from_mesh(mesh))
    named = ([(pc["thickness"], pc.get("name")) for pc in pieces if pc["kind"] == "sheet"]
             + [(2 * pc["half"], pc.get("name")) for pc in pieces if pc["kind"] == "stick"])
    thin = [t for t, _ in named] + ([walls] if walls and walls > 0 else [])
    where: dict = {}
    if thin:
        least = min(thin)
        if walls and walls > 0 and walls == least:
            where = {"at": at} if at else {}
        else:
            where = next(({"piece": n} for t, n in named if t == least and n), {})
    found = [(t, {"piece": n} if n else {}) for t, n in named] + ([(walls, {"at": at} if at else {})] if walls and walls > 0 else [])
    return thin, walls, where, found


def unseen_walls(found: list, spacing: float) -> list[dict]:
    """Every wall the voxels can't see, thinnest first, of any material (#248 review: the run had recorded only its thinnest,
    so a printed wall a little thicker than a thin sheet went uncounted): ``{"mm", "piece"}`` or ``{"mm", "at"}``."""
    return [{"mm": round(t, 2), **w} for t, w in sorted(found, key=lambda x: x[0]) if not _sees(t / spacing)]


def would_see(declared: dict, mesh, pieces: list[dict]) -> dict:
    """Can a check of this shape, at the voxels it would use, see its thinnest wall? ``{"thin_mm", "seen"}`` (#167: what decides how far
    a re-check lands from a study's own number)."""
    thins, walls, _, _ = _thin(declared, mesh, pieces)
    if not thins:
        return {"thin_mm": None, "seen": True}
    spacing, _ = spacing_for(pieces, float(abs(mesh.volume)), float(max(mesh.extents)), walls)
    return {"thin_mm": round(min(thins), 2), "seen": _sees(min(thins) / spacing)}


def study_spacing(declared: dict, mesh, pieces: list[dict]) -> tuple[float, Optional[str]]:
    """The voxel size the strength check analyses this part at (:func:`spacing_for`), from what it declares."""
    _, walls, _, _ = _thin(declared, mesh, pieces)
    return spacing_for(pieces, float(abs(mesh.volume)), float(max(mesh.extents)), walls)


def _sees(across: float) -> bool:
    """Enough voxels across to see a wall: RESOLVE_MIN, give or take a voxel size's rounding (a default run sized at
    exactly RESOLVE_MIN across reads 3.99999)."""
    return across >= RESOLVE_MIN * (1 - 1e-3)


#: What a carve or lightening says where no run a study may make can see the walls (CALI-106, #101), when where
#: they are isn't known; :func:`thin_words` says where, and what to change.
TOO_THIN = "Its walls are too thin for the voxel check at this size, so it can't be carved by strength"


def wall_rule(store: DesignStore, part_id: str) -> Optional[tuple[str, float]]:
    """The part's own rule on its thinnest wall (``min_wall >= …``, its spec's or the design's), and the mm it asks
    for: what the person already said the walls must be (#136 review: the bar stool's locked 2.85 mm)."""
    import re

    from .evaluate import DEFAULT_MACHINE, safe_eval

    spec = store.read_spec(part_id)
    rules = list(spec.assertions if spec else []) + [a for a in store.assembly.assertions if part_id in a.expr]
    for a in rules:
        m = re.match(r"\s*min_wall\s*>=?\s*(.+)$", a.expr)
        if m:
            try:
                return a.id, float(safe_eval(m.group(1), {"machine": DEFAULT_MACHINE}))
            except Exception:  # noqa: BLE001 — a rule this can't read is left out, not guessed at
                continue
    return None


def sees_from(mm: float) -> float:
    """The wall a check can see, to say: rounded up to the tenth, and past a recorded figure's own rounding (#159 review:
    a true 9.207 said as 9.2 came back too thin). One number for the wall everywhere (#137 item 2)."""
    import math

    return math.ceil((mm + 0.05) * 10) / 10


def thin_words(store: DesignStore, part_id: str, thin: float, where: dict, finest_mm: float,
               printed: bool) -> str:
    """Why a study can't run on walls this thin, where they are, and what to change (#136 review), said in two parts
    that ask different things. Printing and the part's own rule: "its 0.25 mm walls around z 16.1 in are too thin
    for a 0.4 mm nozzle to print and for your rule shell_wall_thickness (at least 2.85 mm): thicken them to that."
    The strength check, in mm: "For a strength carve, walls must be at least 9.2 mm at this size, so check it by hand
    or with a test piece instead." (Thickening to 2.85 mm doesn't unblock a carve: only 9.2 mm would.) One number
    for the wall, the same everywhere (#137 item 2)."""
    from .answers import _len, _wall
    from .evaluate import DEFAULT_MACHINE

    inches = getattr(store.design, "display_units", "in") == "in"
    at = (f" in the {where['piece']}" if where.get("piece") else
          f" around z {_len(where['at'][2], inches)}" if where.get("at") else "")
    head, sees = f"its thinnest walls, {_wall(thin)}{at}, are", sees_from(RESOLVE_MIN * finest_mm)
    nozzle = DEFAULT_MACHINE.nozzle
    printing, rule = printed and thin < nozzle, wall_rule(store, part_id)
    need = rule if rule and thin < rule[1] else None
    if not (printing or need):
        return (f"{head} too thin for the strength check to see: at this size it sees walls from {sees:.1f} mm "
                f"on, so check it by hand or with a test piece instead.")
    rule_said = f"your rule {need[0]} (at least {round(need[1], 2):g} mm)" if need else ""
    return (head + (f" too thin for a {nozzle:g} mm nozzle to print" + (f" and for {rule_said}" if need else "")
                    if printing else f" thinner than {rule_said}")
            + (": thicken them to that." if need else ": thicken them.")
            + f" For a strength carve, walls must be at least {sees:.1f} mm at this size, so check it by hand or "
              f"with a test piece instead.")


def resolution(ctx: dict) -> dict:
    """Can this set-up's voxels see the thinnest wall? As the strength check measures it (CALI-97), for the studies
    that share its set-up (carve, lighten: CALI-106): ``thinnest_mm``, ``across``, ``resolved``, and, unresolved,
    ``finer`` (a finer run can see it) or ``too_thin`` (none a study may make can). {} when it can't be told."""
    thin, s = ctx.get("thinnest"), ctx.get("spacing")
    if not thin or not s:
        return {}
    out = {"thinnest_mm": round(thin, 2), "across": round(thin / s, 3), "resolved": _sees(thin / s)}
    if not out["resolved"]:
        want = math.floor(thin / RESOLVE_MIN * 100) / 100
        out.update({"finer": True} if want >= (ctx.get("finest") or 0) else {"too_thin": True})
        if ctx.get("thin_said"):
            out.update({"where": ctx.get("thinnest_where") or {}, "said": ctx["thin_said"]})
    return out


#: how far below the load's own stress a peak may read before the check is taken to have seen nothing (#202): a load has to get through
#: the part, so even spread wide the peak is a fair share of force over footprint. Not on the safety factor: a tiny load is a big one.
#: A floor against nonsense and no more: one voxel layer of a thin foot can read 4 to 7 times high and stay well above it
SEES_STRESS = 0.01


def _nominal(c: dict) -> Optional[float]:
    """The load's own stress: its force over the footprint it's pushed on, in MPa, or None where the case doesn't say."""
    force, lo, hi = c.get("force_n"), c.get("lo"), c.get("hi")
    if not (force and lo and hi):
        return None
    axis = max(range(3), key=lambda i: abs(force[i]))
    a, b = [float(hi[i]) - float(lo[i]) for i in range(3) if i != axis]
    return float(sum(f * f for f in force) ** 0.5) / (a * b) if a > 0 and b > 0 else None


def judged_by(run: dict, case: dict) -> Optional[str]:
    """The check a case's verdict stands on: what governs it. Under a hand buckling check (CALI-159, #229) that's the
    buckling check where it fails (a fail is certain), and where it holds, the check it took over from: a pass from it never
    settles an FEA too coarse to see the wall, blind, or spanning between its holds."""
    governs = case.get("governs", "fea")
    if governs != "buckling":
        return governs
    need = run.get("min_safety") or MIN_SAFETY
    return "buckling" if case.get("safety") is not None and case["safety"] < need else case.get("over", "fea")


def blind(run: dict, case: dict) -> bool:
    """The FEA ran and saw next to no stress for the load it was given: a bracket's 12 mm foot, loaded half way along, read 54,956,221
    times over (#202). That's a check that saw nothing, not a part that holds. No number from it means the same."""
    fea = case.get("fea") or {}
    if fea.get("supported") is not True or judged_by(run, case) != "fea":
        return False
    if "safety" not in fea:           # a case that doesn't say isn't one that saw nothing
        return False
    if fea["safety"] is None:
        return True
    if not fea["safety"]:             # rounded to 0.00: the stress was huge, so it broke. The opposite of seeing nothing
        return False
    material, nominal = run.get("material"), _nominal(case)
    strength = material.get("strength") if isinstance(material, dict) else None
    return bool(strength and nominal) and float(strength) / float(fea["safety"]) < SEES_STRESS * nominal


def unresolved(run: dict, case: dict) -> bool:
    """A verdict the FEA governs at fewer than RESOLVE_MIN voxels across the thinnest wall: too coarse to see it. Or one that saw no
    stress to judge by (:func:`blind`). Or one where another check governs, by being lowest, while the FEA ran and couldn't see a
    printed wall that no hand check covers (CALI-164, #244: the bar stool's seat plate read "holds, 3.31×" over a cone whose 5.8 mm
    wall the voxels couldn't see; its true safety could be under 3.31, so the case is unknown)."""
    if blind(run, case):
        return True
    thin, s = run.get("thinnest_mm"), run.get("spacing_mm")
    if not (thin and s) or _sees(run.get("across") or thin / s):    # as the run counted it, not from its rounded sizes
        return False
    return judged_by(run, case) in FEA or bool(unseen(run, case))


#: The checks that are the FEA's own number: lighten's calibrated one is the FEA's too (#248 review).
FEA = ("fea", "fea-calibrated")


def unseen(run: dict, case: dict) -> str:
    """Where another check governs a case and the FEA, which ran, couldn't see a wall: what couldn't be seen, in words (#244).
    A wall is cleared only by a check of that same piece (#248, the foreman's scope): a sheet's own plate check clears that
    sheet, and nothing else does. A run that doesn't list what it couldn't see is unknown, the safe side. "" when nothing is
    unseen."""
    fea = case.get("fea") or {}
    if judged_by(run, case) in FEA or fea.get("supported") is not True or fea.get("safety") is None:
        return ""
    thin, s = run.get("thinnest_mm"), run.get("spacing_mm")
    if not (thin and s) or _sees(run.get("across") or thin / s):
        return ""
    voxels = f"needs {RESOLVE_MIN:g} voxels across, and these are {s:g} mm"
    pl = case.get("plate") or {}
    cleared = {pl.get("piece")} if pl.get("done") and pl.get("piece") else set()
    walls = run.get("unseen")
    if walls is None:                                  # an older run: only its thinnest is known, and where
        where = run.get("thinnest_where") or {}
        if not where or where.get("piece") in cleared:   # what else it couldn't see isn't known: the safe side
            return (f"this run doesn't say which walls its voxels couldn't see (its thinnest is {thin:g} mm, {voxels}): "
                    f"check it again")
        walls = [{"mm": thin, **where}]
    left = [w for w in walls if w.get("piece") not in cleared or not w.get("piece")]
    if not left:
        return ""
    w = left[0]
    what = f"the {w['piece'].replace('_', ' ')} is" if w.get("piece") else "the printed walls are"
    return f"{what} too thin to check at this size ({w['mm']:g} mm, {voxels})"


def governing_words(case: dict) -> str:
    """The check that governs a case, in words: "the seat's plate check", "the leg's buckling check", "the FEA" (#248 review:
    name it from ``governs``, with its own number)."""
    governs = case.get("governs", "fea")
    if governs == "plate":
        piece = (case.get("plate") or {}).get("piece")
    elif governs == "buckling":
        done = [r for r in case.get("buckling") or [] if r.get("done")]
        piece = min(done, key=lambda r: r["safety"])["piece"] if done else None
    else:
        return "the FEA"
    return f"the {piece.replace('_', ' ')}'s {governs} check" if piece else f"the {governs} check"


def unchecked(run: dict, case: dict) -> bool:
    """Unresolved, and no run a study may make is fine enough to resolve it: not checked (CALI-97)."""
    return unresolved(run, case) and not run.get("finer")


# ---------------------------------------------------------------------------
# Where a load lands (CALI-84): one rule for the designer's check and the strength check
# ---------------------------------------------------------------------------
def reach(tol: float, spacing: float) -> float:
    """How far off the part a load or support box may be and still push on it (or hold it): the measuring
    tolerance, or one voxel of the strength check, whichever is more."""
    return max(spacing, tol)


def touches(mesh, box, reach: float) -> tuple[bool, float]:
    """Whether a box (lo, hi) is on the part: in it, or within ``reach`` of its surface. Also how far it is from
    the nearest surface (0 when it's in the part): from the surface points nearest to points spread through the
    box, back to the box itself. Exact for a box facing a surface; otherwise a little long, never short, so a box
    this passes, grown by ``reach`` and half a voxel, takes voxels in."""
    from . import spatial

    lo, hi = (np.asarray(v, float) for v in box)
    axes = [np.linspace(a, b, int(min(8, max(2, math.ceil((b - a) / max(reach, 0.5)) + 1)))) for a, b in zip(lo, hi)]
    pts = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)

    near, _, _ = spatial.closest_point(mesh, pts)
    gap = float(np.linalg.norm(near - np.clip(near, lo, hi), axis=1).min())
    if gap > reach and spatial.contains(mesh, pts).any():           # a box inside the solid, far from its surface
        gap = 0.0
    return gap <= reach, round(gap, 2)


def missed(name: str, gap: float, reach: float, support: bool = False) -> str:
    """What both checks say when a box isn't on the part."""
    if support:
        return (f"'{name}' doesn't touch the part — nothing holds it there, {gap:.1f} mm from its nearest surface "
                f"(a support may be up to {reach:.1f} mm off it): put its box where the part rests")
    return (f"'{name}' doesn't touch the part — it pushes on thin air, {gap:.1f} mm from its nearest surface "
            f"(a load may be up to {reach:.1f} mm off it): put its box on the face it pushes on")


# ---------------------------------------------------------------------------
# The plate check
# ---------------------------------------------------------------------------
def _interp(x: float, xs: list, ys: list) -> float:
    return float(np.interp(x, xs, ys))


def plate(a: float, b: float, t: float, force: float, footprint: float, E: float) -> dict:
    """A plate a × b (mm) × t, simply supported all round, a central load ``force`` (N) over
    ``footprint`` mm²: the peak stress (MPa) and the deflection (mm) under it. Roark, Table 11.4."""
    a, b = max(a, b), min(a, b)
    r0 = min(math.sqrt(max(footprint, 1.0) / math.pi), b / 2)
    if r0 < 0.5 * t:                        # the equivalent radius for a load on a small spot
        r0 = math.sqrt(1.6 * r0 ** 2 + t ** 2) - 0.675 * t
    beta, alpha = _interp(a / b, _AB, _BETA), _interp(a / b, _AB, _ALPHA)
    stress = 3 * force / (2 * math.pi * t ** 2) * ((1 + POISSON) * math.log(2 * b / (math.pi * r0)) + beta)
    return {"stress_mpa": stress, "deflection_mm": alpha * force * b ** 2 / (E * t ** 3)}


def ring_plate(a: float, t: float, force: float, footprint: float, E: float) -> dict:
    """A round plate simply supported on a ring of radius ``a`` (mm), ``t`` thick, a load ``force`` (N) over a central
    ``footprint`` (mm²): the peak stress (MPa, at the middle) and the deflection (mm) there. Roark (7th ed.) Table 11.2
    case 16, uniform load over a central circle r0 (with Table 11.4's equivalent radius for a small spot):
    σ = 3W/(2πt²)·[(1+ν)·ln(a/r0) + 1 − (1−ν)·r0²/(4a²)], y = W·a²/(16πD)·[(3+ν)/(1+ν)] at most. A disc that runs on
    past its ring is stiffer than this: the safe side. NEEDS ENGINEER CHECK (#137 item 7, against the foreman's hand
    check of the bar stool's seat: 4.5 MPa)."""
    r0 = min(math.sqrt(max(footprint, 1.0) / math.pi), a)
    if r0 < 0.5 * t:                        # the equivalent radius for a load on a small spot
        r0 = math.sqrt(1.6 * r0 ** 2 + t ** 2) - 0.675 * t
    nu = POISSON
    stress = 3 * force / (2 * math.pi * t ** 2) * ((1 + nu) * math.log(a / r0) + 1 - (1 - nu) * r0 ** 2 / (4 * a ** 2))
    D = E * t ** 3 / (12 * (1 - nu ** 2))
    return {"stress_mpa": stress, "deflection_mm": force * a ** 2 / (16 * math.pi * D) * (3 + nu) / (1 + nu)}


def _ring_held(pc: dict, k: int, under, tol: float) -> Optional[float]:
    """The radius (mm) of the widest ring under a round panel that the part beneath holds all the way round (90% of
    it), measured from the panel's middle: a disc on a cone's top ring. The widest: a longer span bends more, the safe
    side. None where nothing beneath holds a ring."""
    from .consistency import _frame

    poly, side, t = pc["polys"][k], pc["sides"][k], pc["thickness"]
    o, u, v, n, flat = _frame(poly)
    mid = poly.mean(axis=0)
    rim = float(np.linalg.norm(poly - mid, axis=1).max())
    ang = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    held = None
    for r in np.arange(max(t, 1.0), rim + 1e-6, 1.0):
        # just under the panel, and only what touches it: a cone flares below its top ring, so a deeper or looser probe
        # reads the ring wider than where it meets the seat (the bar stool: 282 mm, against its 266 mm ring)
        pts = (mid + r * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
               + side * n * (t + 1.0))
        if float(np.mean(under(pts, 0.5))) >= 0.9:
            held = float(r)
    return held


def _round(poly: np.ndarray) -> bool:
    """A panel drawn as a disc: eight or more sides, every corner within a tenth of the same radius."""
    if len(poly) < 8:
        return False
    r = np.linalg.norm(poly - poly.mean(axis=0), axis=1)
    return float(r.min()) >= 0.9 * float(r.max())


#: How far either side of a load a panel on two edges carries it, as a share of the span: BS 8110-1:1997 clause
#: 3.5.2.2 (a concentrated load on a slab spanning one way) gives the load's width + 2.4·x·(1 - x/L) for a load x
#: from a support, so 0.6·L at mid-span; near an unsupported edge, no more than half that plus the load's distance
#: from the edge. (DIN 1045 Heft 240 gives 0.625·L at mid-span.) NEEDS ENGINEER CHECK: read from the clause as the
#: reviewer and the foreman both understand it, not yet checked against the printed text. Against the Lévy plate
#: solution (tests/test_beam_width.py) it reads 31% high in stress on a panel three spans wide and 23% high at 1.5
#: spans: the safe side (CALI-86).
BEAM_SPREAD = 0.6


def beam(span: float, width: float, t: float, force: float, mat: dict, footprint: float = 0.0,
         edge: Optional[float] = None, grain: Optional[str] = None, span_axis: Optional[str] = None) -> dict:
    """A panel resting on two opposite edges, the load (``footprint`` mm wide along the edges, its middle ``edge`` mm
    from the nearer free end; the middle if not given) in the middle of its span: a simply supported beam (the safe
    side: the edges free to turn, the load not spread along the span), as wide as carries the load: the panel, or
    BS 8110's effective width if that's less (:data:`BEAM_SPREAD`). Stress, sag and safety, and at other
    thicknesses, all at that width. ``grain``: which way its face grain runs, "along" or "across" the span, only as
    the person said it (CALI-126): that grain's number and sag govern; not said, the worse of the two (#118)."""
    spread = footprint + BEAM_SPREAD * span
    carries = min(width, spread, 0.5 * spread + (width / 2 if edge is None else max(edge, 0.0)))
    # CALI-116 (#118): BS 8110's width is for an isotropic slab; cl. 3.5.2.2(b) takes less where the panel is less
    # stiff across the span than along it. Plywood with its face grain along the span is: its width shrinks by
    # (D_across / D_along)^(1/4), the panel's two moduli (about 0.84 for ply, half as stiff across). With the grain
    # across the span the isotropic width is the safe side. NEEDS ENGINEER CHECK (#42: or an orthotropic plate's
    # b_ef = M_beam / m_plate, or let the plate check govern).
    # The whole effective width takes the factor (the edge's share too: the slab beside the foot spreads it by the
    # same stiffness), still never past the panel's own width.
    k = orthotropic(mat)
    along = min(width, k * spread, k * (0.5 * spread + (width / 2 if edge is None else max(edge, 0.0))))

    def at(tt, b):
        stress = force * span / 4 / (b * tt ** 2 / 6)
        sag = force * span ** 3 / (48 * mat["E"] * b * tt ** 3 / 12)
        return stress, sag

    def both(tt):
        """(safety with the grain along the span, at its narrower width; with the grain across, at the slab's)."""
        return mat["strength"] / at(tt, along)[0], mat["strength"] * mat.get("across", 1.0) / at(tt, carries)[0]

    from . import grain as G

    # one phrase for the cut, led by the part's own direction where the span's is known (#151 review)
    advice = G.phrase(G.runs(span_axis, "along"), "along")
    said = G.phrase(G.runs(span_axis, grain), grain) if grain in G.GRAINS else None
    # the sag beside "grain unknown" is the worse grain's, as its safety is (#122 review): with the grain along the
    # span, the panel's own E on the narrower width; across it, its stiffness across the face grain on the whole width
    e_across = (mat["E_across"] / mat["E"]) if mat.get("E_across") else mat.get("across", 1.0)

    def sag_worse(tt):
        return max(at(tt, along)[1], at(tt, carries)[1] / max(min(e_across, 1.0), 1e-6))

    def sag_of(tt):                          # the said grain's sag, else the worse grain's
        return (at(tt, along)[1] if grain == "along" else
                at(tt, carries)[1] / max(min(e_across, 1.0), 1e-6) if grain == "across" else sag_worse(tt))

    def governs(g, w):                       # the said grain's safety, else the worse of the two (#118)
        return g if grain == "along" else w if grain == "across" else min(g, w)

    stress, sag = at(t, carries)[0], sag_of(t)
    good, wrong = both(t)
    by_t = []
    for tt in C.THICKNESSES:
        if tt > 26:
            continue
        g, w = both(tt)
        by_t.append({"thickness_mm": tt, "label": M.nominal(tt), "safety": V.cut(g),
                     "safety_across": V.cut(governs(g, w)), "deflection_mm": round(sag_of(tt), 3)})
    return {"done": True, "as": "beam", "span_mm": round(span, 1), "thickness_mm": t, "stress_mpa": round(stress, 2),
            # the grain's way unknown, the verdict takes the worse of the two (#118); said, that grain's (CALI-126)
            "safety": V.cut(good), "safety_across": V.cut(governs(good, wrong)),
            "grain": grain if grain in ("along", "across") else None,
            "grain_phrase": said, "advice_phrase": advice,
            "deflection_mm": round(sag, 3), "by_thickness": by_t, "width_mm": round(carries, 1),
            # each grain's sag, for a reader that knows which way it runs (the real test's prediction: #122 review)
            "deflection_along_mm": round(at(t, along)[1], 3),
            "deflection_across_mm": round(at(t, carries)[1] / max(min(e_across, 1.0), 1e-6), 3),
            "width_along_mm": round(along, 1), "orthotropic": round(k, 3),
            "why": f"it rests on two opposite edges, {span / 25.4:.1f} in apart: a beam across them"
                   + (f", {carries / 25.4:.1f} in of it carrying the load (BS 8110's effective width for a load "
                      f"{'this near its free end' if carries < min(width, spread) else 'on a panel this wide'})"
                      if carries < width else "")
                   + (f". With its {said}, as you said: about {good if grain == 'along' else wrong:.1f} times over"
                      if said and mat.get("across", 1.0) < 1.0
                      else f". Cut with its {advice} and it's about {good:.1f} times over instead of {wrong:.1f}"
                      + (f" (on {along / 25.4:.1f} in: cut that way it's less stiff across, so less of it carries "
                         f"the load)" if along < carries else "")
                      if mat.get("across", 1.0) < 1.0 else "")}


def orthotropic(mat: dict) -> float:
    """(D_across / D_along)^(1/4) for a sheet: its stiffness across the face grain over along it (CALI-116). The
    material's own E_across if it gives one, else its strength ratio across (ply: about half, both ways); 1 for a
    material the same both ways."""
    across = mat.get("E_across")
    ratio = (across / mat["E"]) if across else mat.get("across", 1.0)
    return float(min(1.0, max(ratio, 0.0)) ** 0.25)


def with_held(under, held: list[dict], tol: float):
    """What a panel rests on, with the part's own ``held()`` patches counted too (CALI-153): a shelf on two patches is a
    beam across them. The floor a part is held by when it doesn't say isn't one: anything would rest on that."""
    boxes = [(np.asarray(h["lo"], float) - 3 * tol, np.asarray(h["hi"], float) + 3 * tol)
             for h in held if not h.get("default")]
    if not boxes:
        return under

    def either(pts, *rest):
        pts = np.asarray(pts, float)
        on = np.any([np.all((pts >= lo) & (pts <= hi), axis=1) for lo, hi in boxes], axis=0)
        return on | under(pts, *rest) if under is not None else on

    return either


def _held_edges(pc: dict, k: int, others: list[dict], tol: float, under=None) -> list[int]:
    """Which of a panel's edges another piece holds: one it butts against, or one under it (up to a
    fifth of the way in: a top that overhangs its sides by an inch still rests on them)."""
    from .consistency import _frame, segment_distance, slab_distance

    poly = pc["polys"][k]
    side, t = pc["sides"][k], pc["thickness"]
    o, u, v, n, flat = _frame(poly)
    centre = poly.mean(axis=0)
    held = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        mid = (p + q) / 2
        inward = centre - mid
        inward -= (inward @ n) * n
        inward /= np.linalg.norm(inward) or 1.0
        reach = max(t, min(0.2 * float(((poly - mid) @ inward).max()), 100.0))
        probes = np.array([mid - inward * 2 * tol + side * n * t / 2]        # beside the edge
                          + [mid + inward * dist + side * n * (t + 2 * tol)  # under it
                             for dist in np.arange(t / 2, reach + 1e-6, t / 2)])
        if under is not None and under(probes[1:]).any():      # resting on the printed solid (CALI-82)
            held.append(i)
            continue
        for other in others:
            if other["kind"] == "sheet":
                d = min(slab_distance(probes, op, other["thickness"], s).min()
                        for op, s in zip(other["polys"], other["sides"]))
            else:
                d = float((segment_distance(probes, other["a"], other["b"]) - other["half"]).min())
            if d <= tol:
                held.append(i)
                break
    return held


#: How near a free edge a foot's box must come to count as standing at that edge (CALI-94): half an inch.
AT_EDGE_MM = 12.7


def two_sided(pieces: list[dict], load: dict, tol: float, under=None) -> Optional[dict]:
    """The sheet a downward load lands on face-on, if it's held on just two opposite edges (a top on two sides,
    CALI-82): ``{"piece", "free": how far the load's box is from the nearer free edge, mm}``. None otherwise."""
    from .consistency import _frame, _inside2d

    lo, hi = np.asarray(load["lo"], float), np.asarray(load["hi"], float)
    c = (lo + hi) / 2
    f = np.asarray(load["force"], float)
    fmag = float(np.linalg.norm(f)) or 1.0
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    for pc in pieces:
        if pc["kind"] != "sheet":
            continue
        for k, poly in enumerate(pc["polys"]):
            o, u, v, n, flat = _frame(poly)
            rel = c - o
            depth = abs(float((hi - lo) @ np.abs(n))) / 2
            if (abs(float(rel @ n)) > pc["thickness"] + depth + tol
                    or not _inside2d(np.array([[rel @ u, rel @ v]]), flat)[0]
                    or abs(float(f @ n)) < 0.7 * fmag):
                continue
            which = _held_edges(pc, k, [x for x in pieces if x is not pc], tol, under)
            if len(poly) != 4 or sorted(which) not in ([0, 2], [1, 3]):
                return None
            box = np.array([[(p - o) @ u, (p - o) @ v] for p in corners])
            umin, vmin = box.min(axis=0)
            umax, vmax = box.max(axis=0)
            gaps = []
            for i in (j for j in range(4) if j not in which):
                a, b = poly[i], poly[(i + 1) % 4]
                pts = [((a + (b - a) * s) - o) for s in np.linspace(0, 1, 65)]
                gaps.append(min(float(np.hypot(max(umin - p @ u, 0, p @ u - umax), max(vmin - p @ v, 0, p @ v - vmax)))
                                for p in pts))
            return {"piece": pc["name"], "free": round(min(gaps), 1)}
    return None


def fea_safety(worked: float) -> Optional[float]:
    """The FEA's number, from its worst voxel's stress over strength: cut toward safe, never rounded up, since the
    case's "holds" is compared from it (CALI-152, #213)."""
    return V.cut(1.0 / worked) if worked > 0 else None


def plate_check(pieces: list[dict], load: dict, mat: dict, tol: float, under=None) -> Optional[dict]:
    """The sheet a load pushes on face-on, checked as a plate — or None if it lands on no sheet, or on
    one that isn't held all round (the FEA is the number for that one)."""
    from .consistency import _frame, _inside2d

    lo, hi = np.asarray(load["lo"]), np.asarray(load["hi"])
    c = (lo + hi) / 2
    f = np.asarray(load["force"], float) * load["factor"]
    fmag = float(np.linalg.norm(f))
    for pc in pieces:
        if pc["kind"] != "sheet":
            continue
        for k, poly in enumerate(pc["polys"]):
            o, u, v, n, flat = _frame(poly)
            rel = c - o
            depth = abs(float((hi - lo) @ np.abs(n))) / 2
            if (abs(float(rel @ n)) > pc["thickness"] + depth + tol
                    or not _inside2d(np.array([[rel @ u, rel @ v]]), flat)[0]
                    or abs(float(f @ n)) < 0.7 * fmag):
                continue
            others = [x for x in pieces if x is not pc]
            which = _held_edges(pc, k, others, tol, under)
            edges = len(which)
            a, b = C.min_rect(flat.tolist())
            ext = hi - lo
            fu, fv = abs(float(ext @ np.abs(u))), abs(float(ext @ np.abs(v)))
            base = {"piece": pc["name"], "a_mm": round(a, 1), "b_mm": round(b, 1),
                    "edges": len(poly), "edges_held": edges, "footprint_mm": [round(fu, 1), round(fv, 1)]}
            if len(poly) == 4 and sorted(which) in ([0, 2], [1, 3]):
                # held on two opposite edges (a top on two sides): a beam across them (CALI-82)
                e0, e1 = poly[which[0]], poly[(which[0] + 1) % 4]
                along = (e1 - e0) / (np.linalg.norm(e1 - e0) or 1.0)
                far = poly[(which[0] + 2) % 4] - e0
                span = float(np.linalg.norm(far - (far @ along) * along))
                width = float(np.linalg.norm(e1 - e0))
                at = float((c - e0) @ along)                 # where the load's middle is along the held edges
                gap = (far - (far @ along) * along) / (span or 1.0)      # which way it spans (CALI-126)
                axis = "xyz"[int(np.argmax(np.abs(gap)))]
                return {**base, **beam(span, width, pc["thickness"], float(abs(f @ n)), mat,
                                       footprint=abs(float(ext @ np.abs(along))),
                                       edge=min(at, width - at), grain=pc.get("grain"), span_axis=axis),
                        "span_axis": axis,
                        **({"grain_assumed": pc["grain_assumed"]} if pc.get("grain_assumed") else {})}
            if _round(poly):                      # a disc: on a ring beneath it, or held all round (#137 item 7)
                mid = poly.mean(axis=0)
                ring = _ring_held(pc, k, under, tol) if under is not None else None
                if ring is None and edges == len(poly):
                    ring = float(np.linalg.norm(poly - mid, axis=1).max())
                off = float(np.linalg.norm((c - mid) - ((c - mid) @ n) * n))
                if ring is not None and off <= 0.25 * ring:
                    t = pc["thickness"]
                    # the pad's own area in the panel's plane: a disc's frame runs diagonal to the load's box, and
                    # measured along it the bar stool's 4 in pad read 119.5 mm across (larger, so less stress)
                    flat_ext = [float(ext[i]) for i in range(3) if i != int(np.argmax(np.abs(n)))]
                    W, foot = float(abs(f @ n)), max(abs(flat_ext[0] * flat_ext[1]), 1.0)
                    got = ring_plate(ring, t, W, foot, mat["E"])
                    safety = mat["strength"] / got["stress_mpa"]
                    by_t = [{"thickness_mm": tt, "label": M.nominal(tt),
                             "safety": V.cut(mat["strength"] / g["stress_mpa"]),
                             "safety_across": V.cut(mat["strength"] * mat["across"] / g["stress_mpa"]),
                             "deflection_mm": round(g["deflection_mm"], 3)}
                            for tt in C.THICKNESSES if tt <= 26
                            for g in [ring_plate(ring, tt, W, foot, mat["E"])]]
                    return {**base, "done": True, "support": "ring", "ring_mm": round(2 * ring, 1),
                            "thickness_mm": t, "stress_mpa": round(got["stress_mpa"], 2),
                            "safety": V.cut(safety), "safety_across": V.cut(safety * mat["across"]),
                            "deflection_mm": round(got["deflection_mm"], 3), "by_thickness": by_t}
                return {**base, "done": False,
                        "why": ("the load is off its middle; the round-plate check covers a load near the middle"
                                if ring is not None else "nothing beneath holds it in a ring all the way round")
                               + ", so the FEA is the number for it"}
            if edges < len(poly) or len(poly) != 4:
                return {**base, "done": False,
                        "why": (f"only {edges} of its {len(poly)} edges rest on another piece; the plate check covers "
                                f"a panel held all round" if edges < len(poly) else
                                f"it's held all round, but its {len(poly)}-sided outline isn't a rectangle or a disc, "
                                f"which the plate check covers")  # never "16 of its 16 edges" (#137 item 7)
                               + ", so the FEA is the number for it"}
            t = pc["thickness"]
            got = plate(a, b, t, float(abs(f @ n)), max(fu * fv, 1.0), mat["E"])
            safety = mat["strength"] / got["stress_mpa"]
            by_t = []
            for tt in C.THICKNESSES:
                if tt > 26:
                    continue
                g = plate(a, b, tt, float(abs(f @ n)), max(fu * fv, 1.0), mat["E"])
                by_t.append({"thickness_mm": tt, "label": M.nominal(tt),
                             "safety": V.cut(mat["strength"] / g["stress_mpa"]),
                             "safety_across": V.cut(mat["strength"] * mat["across"] / g["stress_mpa"]),
                             "deflection_mm": round(g["deflection_mm"], 3)})
            return {**base, "done": True, "thickness_mm": t, "stress_mpa": round(got["stress_mpa"], 2),
                    "safety": V.cut(safety), "safety_across": V.cut(safety * mat["across"]),
                    "deflection_mm": round(got["deflection_mm"], 3), "by_thickness": by_t}
    return None


# ---------------------------------------------------------------------------
# The FEA, and the picture
# ---------------------------------------------------------------------------
def _grow(lo, hi, by: float):
    return (tuple(float(v) - by for v in lo), tuple(float(v) + by for v in hi))


def heat_mesh(mesh, grid, von_mises: np.ndarray, solid: np.ndarray, max_edge: float) -> dict:
    """The part's own surface, split finely enough to carry a stress per vertex: the worst of the voxels
    around each vertex. Base64 typed arrays, as three.js takes them."""
    import trimesh

    v, f = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    for _ in range(6):
        try:
            v2, f2 = trimesh.remesh.subdivide_to_size(v, f, max_edge=max_edge, max_iter=12)
        except ValueError:
            v2, f2 = v, f
        if len(f2) <= 400_000:
            break
        max_edge *= 1.5
    v, f = v2, f2
    vm = np.where(solid, von_mises, 0.0)
    shape = np.asarray(vm.shape)
    low = np.floor((v - np.asarray(grid.origin)) / grid.spacing).astype(np.int64)
    heat = np.zeros(len(v))
    for corner in np.ndindex(2, 2, 2):
        cell = low + np.asarray(corner)
        ok = np.all((cell >= 0) & (cell < shape), axis=1)
        vals = np.zeros(len(v))
        cc = cell[ok]
        vals[ok] = vm[cc[:, 0], cc[:, 1], cc[:, 2]]
        heat = np.maximum(heat, vals)

    def b64(a):
        return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")

    return {"positions": b64(v.astype(np.float32)), "index": b64(f.astype(np.uint32)),
            "heat": b64(heat.astype(np.float32)), "max": float(heat.max()) if len(heat) else 0.0}


def plate_why(pl: Optional[dict]) -> Optional[str]:
    """Why a plate check didn't run, from the record's numbers: a run from before #137 stored "only 16 of its 16 edges
    rest on another piece" for a panel held all round (#139 review). Its own words otherwise."""
    pl = pl or {}
    if pl.get("done") or not pl.get("why"):
        return pl.get("why")
    edges, held = pl.get("edges"), pl.get("edges_held")
    if edges is not None and held is not None and held >= edges and "of its" in pl["why"]:
        return (f"it's held all round, but its {edges}-sided outline isn't one the plate check covered when this ran; "
                f"check it again for a round plate's number")
    return pl["why"]


#: What the check can't see, said wherever a wall carries the load in compression and isn't checked by hand (#70 item 5):
#: a printed part's walls, or a sheet :mod:`buckling` can't describe (CALI-159).
BUCKLING = ("Buckling isn't checked: a thin wall carrying the load in compression can fold before it reaches its "
            "strength, more so with a big cut-out.")
#: Said where every sheet in line with a load was checked for it by hand (CALI-159, #229).
BUCKLING_CHECKED = ("Buckling is checked by hand for each wall the load runs down: as a flat plate, its whole load on it, "
                    "its edges free where nothing meets them, and the plywood taken the weaker way (rough).")


def buckling_notes(pieces: list[dict], loads: list[dict], mat: dict, tol: float = 2.0,
                   sheet_mat: Optional[dict] = None) -> list[str]:
    """What's said of buckling, if the part has a wall to carry a load in its own plane: :data:`BUCKLING` for a printed
    part, or where a sheet in line with a load couldn't be checked (naming it, and why); else :data:`BUCKLING_CHECKED`."""
    if mat.get("printed"):
        return [BUCKLING]
    from . import buckling as B

    rows = [r for ld in loads for r in B.check(pieces, ld, sheet_mat or mat, tol)]
    if not rows:
        return []
    left = {}
    for r in rows:
        if not r["done"]:
            left.setdefault(r["piece"], r["why"])
    if left:
        return [BUCKLING + " Not on " + "; ".join(f"the {p}: {why}" for p, why in left.items()) + "."]
    return [BUCKLING_CHECKED]


#: The share of a load's own footprint over a hold at which it's a push straight down, not a span.
ON_A_HOLD = 0.5


def _closed_round(held: set, at: tuple) -> bool:
    """Whether walking out from ``at`` in all four directions meets something held, past any hold it starts on."""
    reach = max(max(abs(a - b) for a, b in zip(c, at)) for c in held) + 1
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        k, clear = 0, False
        met = False
        while k <= reach:
            here = (at[0] + dx * k, at[1] + dy * k) in held
            clear = clear or not here
            if clear and here:
                met = True
                break
            k += 1
        if not met:
            return False
    return True


def spans_between(patches: list, lo, hi, force, spacing: float) -> bool:
    """Whether a load bends the part between where it's held, seen along the load (CALI-153, #217). Its middle is inside the outline of everything
    that's held (not past it, like a bracket's arm); under half of its own footprint lands over a hold (not a leg pushed straight down, but a load
    spread over three feet is); and the holds don't close all round it (a ring or a box's walls carry it down). Feet joined into one patch still
    span. ``patches``: the held places, as points a voxel apart."""
    if not len(patches):
        return False
    from shapely.geometry import MultiPoint, Point

    keep = [i for i in range(3) if i != int(np.argmax(np.abs(np.asarray(force, float))))]
    lo2, hi2 = np.asarray(lo, float)[keep], np.asarray(hi, float)[keep]
    mid = (lo2 + hi2) / 2
    points = np.unique(np.vstack(patches)[:, keep], axis=0)
    if not Point(mid).within(MultiPoint(points).convex_hull.buffer(spacing)):
        return False
    origin = points.min(axis=0)
    cell = lambda xy: tuple(np.rint((np.asarray(xy, float) - origin) / spacing).astype(np.int64).tolist())        # noqa: E731
    held = {cell(p) for p in points}
    axes = [np.arange(a, b + spacing / 2, spacing) if b > a else np.array([a]) for a, b in zip(lo2, hi2)]
    foot = [cell((x, y)) for x in axes[0] for y in axes[1]]
    if sum(c in held for c in foot) / len(foot) >= ON_A_HOLD:
        return False
    return not _closed_round(held, cell(mid))


def _held_patches(ctx: dict) -> list:
    """Where the part is held, as separate patches of voxel centres, however many ``held()`` said (or the floor's feet)."""
    from scipy import ndimage

    ls, held, grow = ctx["ls"], ctx["held"], ctx["grow"]
    region = np.zeros(ls.grid.shape, dtype=bool)
    for h in held:
        region |= ls.region(box=_grow(h["lo"], h["hi"], grow))
    labels, n = ndimage.label(region, structure=np.ones((3, 3, 3)))
    origin = np.asarray(ls.grid.origin, float)
    return [origin + ls.grid.spacing * np.argwhere(labels == i + 1) for i in range(n)]


def _spans(run: dict, c: dict) -> bool:
    """Whether a case's load spans between its holds: as the run recorded, or, from before it did, from its ``held()`` boxes. A
    stored run held by the default floor can't tell, and says nothing new until it's checked again."""
    if "spans" in c:
        return bool(c["spans"])
    boxes = [h for h in run.get("held") or [] if not h.get("default") and h.get("lo") and h.get("hi")]
    if len(boxes) < 2 or not (c.get("lo") and c.get("hi") and c.get("force_n")):
        return False
    step = float(run.get("spacing_mm") or 1.0)
    patches = [np.stack(np.meshgrid(*[np.arange(a, b + step / 2, step) if b > a else np.array([a]) for a, b in zip(h["lo"], h["hi"])],
                                    indexing="ij"), -1).reshape(-1, 3) for h in boxes]
    return spans_between(patches, c["lo"], c["hi"], c["force_n"], step)


def fixed_ends(run: dict, c: dict) -> bool:
    """Whether this case's verdict rests on an FEA holding the ends of a span fixed, with no plate or beam check behind it, and a number that
    wouldn't clear what it needs if the FEA reads as high as it can (:data:`verdicts.SPAN_MARGIN`): not a ✓ (CALI-153: a shelf on two patches
    read 5.06 where beam theory gives about 1). ``run`` needs ``min_safety``."""
    safety, need = c.get("safety"), run.get("min_safety") or MIN_SAFETY
    return (judged_by(run, c) == "fea" and not (c.get("plate") or {}).get("done")
            and (c.get("fea") or {}).get("supported") is not False and safety is not None and safety < need * V.SPAN_MARGIN
            and _spans(run, c))


def run_safety(cases: list) -> Optional[float]:
    """A strength run's number, as ``study`` writes it: the worst of the cases that ran. A case whose load never
    reached a support has none, so it's never a 0x (#140 review); none that ran, no number."""
    return min((c["safety"] for c in cases if c.get("safety") is not None
                and (c.get("fea") or {}).get("supported") is not False), default=None)


def peak_in(fea: Optional[dict]) -> Optional[str]:
    """Where a run's hottest voxel is, by name, only from a run that recorded the wall there (``wall_mm``, #137): an
    older run named the nearest wood even for a hot spot in a printed part (the bar stool's "seat top" was the cone)."""
    fea = fea or {}
    return fea.get("in") if "wall_mm" in fea else None


def _printed_name(declared: dict) -> Optional[str]:
    """What the part's printed share is called in its construction() ("cone"), or None if nothing's printed."""
    for it in declared.get("construction") or []:
        if isinstance(it, dict) and it.get("kind") == "printed":
            return str(it.get("name") or "printed part")
    return None


def _nearest_piece(point: np.ndarray, pieces: list[dict], within: Optional[float] = None,
                   otherwise: Optional[str] = None) -> Optional[str]:
    """The sheet or stick a point is in. With ``within``, only one it's in or that near, else ``otherwise``: a printed
    part isn't a piece, so its hot voxel took the nearest wood's name, 330 mm away (#137: the bar stool's "seat top"
    at z 389 mm, in the cone's webs)."""
    from .consistency import segment_distance, slab_distance

    best = None
    for pc in pieces:
        if pc["kind"] == "sheet":
            d = min(float(slab_distance(point[None], p, pc["thickness"], s)[0])
                    for p, s in zip(pc["polys"], pc["sides"]))
        else:
            d = float(segment_distance(point[None], pc["a"], pc["b"])[0]) - pc["half"]
        if best is None or d < best[0]:
            best = (d, pc["name"])
    if within is not None and (best is None or best[0] > within):
        return otherwise
    return best[1] if best else otherwise


# ---------------------------------------------------------------------------
# Running it, and keeping the results with the design
# ---------------------------------------------------------------------------
def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "loads")


def prepare(store: DesignStore, part_id: str, emit: Optional[Callable] = None, spacing: Optional[float] = None) -> dict:
    """Everything a strength check of this part needs, set up once: its loads, pieces and material, the
    voxels, where it's held. Shared by :func:`study` and the lightening study (``lighten.py``)."""
    from whittle import LoadStudy, Material, Mesh

    from .consistency import _sides, shapes, tolerance

    emit = emit or (lambda *a, **k: None)
    declared = C.declared(store, part_id)
    if not declared.get("loads"):
        raise ValueError(f"'{part_id}' doesn't say what it must hold: its script has no loads()")
    # a tipping case is the tip check's (statics), not a strength case (CALI-98)
    strength = [ld for ld in declared["loads"] if not (isinstance(ld, dict) and ld.get("tip"))]
    if not strength:
        raise ValueError(f"'{part_id}' only says how it might tip, not what it must hold: add a load that isn't a tip")
    loads = parse_loads(strength)
    mesh = store.part_geometry(part_id).require_mesh()
    from .measure import closed, open_near

    if not closed(mesh):                       # said where, never a throw from deep in a boolean (CALI-118)
        raise ValueError(f"not checked: its shape isn't closed {open_near(mesh)}, so it can't be voxelized")
    pieces = shapes(declared)
    said = (store.design.grain or {}).get(part_id) or {}  # the grain the person said, per panel (CALI-126)
    for pc in pieces:
        if pc["kind"] == "sheet":
            pc["grain"] = (said.get(pc["name"]) or {}).get("grain")
    rest = C.printed_solid(store, part_id, declared)       # what's printed: the whole part, or the rest (CALI-82)
    printed = printed_material(declared, mesh, rest)       # a printed part (CALI-81)
    wood = [pc for pc in pieces if pc["kind"] in ("sheet", "stick")]
    sheet_mat = material(wood) if wood else None
    mat = printed or sheet_mat or material(pieces)
    _sides(mesh, pieces)
    tol = tolerance(mesh)
    thins, walls, where, found = _thin(declared, mesh, pieces)
    volume, longest = float(abs(mesh.volume)), float(max(mesh.extents))
    least = finest(volume, longest, FINER_BUDGET)       # as fine as any run of it may go (CALI-97)
    if spacing is None:
        spacing, coarse = spacing_for(pieces, volume, longest, walls)
    elif spacing < least:                               # asked for finer than a study may take: as fine as it may
        coarse = (f"Asked for {spacing:g} mm voxels, finer than a study of a part this size may take: it ran at "
                  f"{least:.2f} mm.")
        spacing = least
    else:                                               # asked for: a finer run (CALI-97)
        coarse = None
    held = parse_held(declared.get("held"), mesh.bounds.tolist(), max(spacing * 0.6, 1.0))
    # the designer's check (loads_land) asks the same question, so the two never disagree (CALI-84)
    rch = reach(tol, spacing)
    for item, support in [(h, True) for h in held] + [(ld, False) for ld in loads]:
        on, gap = touches(mesh, (item["lo"], item["hi"]), rch)
        if not on:
            raise ValueError(missed(item["name"], gap, rch, support))

    emit("voxels", f"voxelizing '{part_id}' at {spacing:.1f} mm in {mat['name']}")
    wmat = Material(name=mat["name"], youngs_modulus=mat["E"], poisson_ratio=POISSON,
                    strength=mat["strength"], density=mat["density"])
    ls = LoadStudy(Mesh(np.asarray(mesh.vertices, float), np.asarray(mesh.faces)), material=wmat,
                   spacing=spacing)
    # a box within reach of a face takes the voxels just under it: half a voxel more, so the layer under even a
    # thin box can't fall between voxel centres
    grow = rch + spacing / 2
    thin = (f"' touches the part only where it's thinner than a voxel ({spacing:.1f} mm), so the strength check "
            f"has nothing there to work with")
    try:
        for h in held:
            ls.support(box=_grow(h["lo"], h["hi"], grow))
    except ValueError:
        raise ValueError(f"'{h['name']}" + thin)
    attach = np.zeros(ls.grid.shape, dtype=bool)
    for h in held:
        attach |= ls.region(box=_grow(h["lo"], h["hi"], grow))
    boxes = []
    for load in loads:
        box = _grow(load["lo"], load["hi"], grow)
        try:
            attach |= ls.region(box=box)
        except ValueError:
            raise ValueError(f"'{load['name']}" + thin)
        boxes.append(box)
    ctx = {"declared": declared, "loads": loads, "boxes": boxes, "mesh": mesh, "pieces": pieces,
           "mat": mat, "tol": tol, "spacing": spacing, "coarse": coarse, "held": held, "ls": ls,
           "thinnest": min(thins) if thins else None, "finest": least, "thinnest_where": where, "found": found,
           "thin_said": thin_words(store, part_id, min(thins), where, least, bool(printed)) if thins else None,
           "attach": attach, "plate_mat": sheet_mat or mat, "grow": grow}
    ctx["patches"] = _held_patches(ctx)
    if printed and wood:
        _two_materials(ctx, wood, sheet_mat, rest)
    return ctx


def per_voxel(ls) -> bool:
    """Whether this whittle takes a stiffness per voxel (greentheo/whittle, after 5363df5)."""
    return hasattr(ls, "stiffness")


def _two_materials(ctx: dict, wood: list[dict], sheet_mat: dict, rest) -> None:
    """CALI-82: a plywood top on printed sides. The voxels in a declared sheet or stick are that material, the
    rest printed: each with its stiffness (whittle's stiffness per voxel, where it has it) and judged against
    its own strength. The plate check counts an edge held where the printed solid is under it."""
    from .consistency import segment_distance, slab_distance

    ls, mat, s = ctx["ls"], ctx["mat"], ctx["spacing"]
    idx = np.argwhere(ls.solid)
    centres = np.asarray(ls.grid.origin) + s * idx               # as the rest of the study places voxels
    inside = np.zeros(len(idx), dtype=bool)
    for pc in wood:
        if pc["kind"] == "sheet":
            for poly, side in zip(pc["polys"], pc["sides"]):
                inside |= slab_distance(centres, poly, pc["thickness"], side) <= s * 0.5
        else:
            inside |= segment_distance(centres, pc["a"], pc["b"]) - pc["half"] <= s * 0.5
    strength = np.full(ls.grid.shape, mat["strength"], dtype=float)
    strength[tuple(idx[inside].T)] = sheet_mat["strength"]
    stiff = np.ones(ls.grid.shape)
    stiff[tuple(idx[inside].T)] = sheet_mat["E"] / mat["E"]
    if per_voxel(ls):                                       # whittle with a stiffness per voxel
        ls.stiffness = stiff
        ctx["note"] = (f"Two materials: the {sheet_mat['name']} as {sheet_mat['name']} and the rest as "
                       f"{mat['name']}, each voxel judged against its own strength.")
    else:
        ctx["note"] = (f"Two materials, judged each against its own strength, but analysed at {mat['name']}'s "
                       f"stiffness throughout (this whittle has no stiffness per voxel): the "
                       f"{sheet_mat['name']} reads softer than it is.")
    ctx["strength_map"] = strength
    if rest is not None:
        from . import spatial

        near = spatial.Proximity(rest)
        # inside the printed solid (trimesh: positive inside), or within tolerance of it
        ctx["under"] = lambda pts, tol=ctx["tol"]: near.signed_distance(np.asarray(pts, float)) >= -tol


def _peak_in(ctx: dict, at: np.ndarray, spacing: float) -> dict:
    """Where the hottest voxel is (``in``: a piece, or the printed part) and the wall it's in (``wall_mm``): a printed
    one measured near it, within two voxels; a piece's own thickness. So a line can say whether the worst stress is
    among walls too thin for the voxels to see (#137 item 2)."""
    printed = _printed_name(ctx["declared"])
    name = _nearest_piece(at, ctx["pieces"], within=spacing if printed else None, otherwise=printed)
    pc = next((p for p in ctx["pieces"] if p["name"] == name), None)
    if pc is not None:
        wall = pc["thickness"] if pc["kind"] == "sheet" else 2 * pc["half"]
    elif printed:
        from .measure import Geometry, wall_near, wall_samples

        if "_walls" not in ctx:                   # sampled once per set-up: every case and carve step shares it
            ctx["_walls"] = wall_samples(Geometry.from_mesh(ctx["mesh"]), samples=20000)
        wall = wall_near(None, at, 2 * spacing, walls=ctx["_walls"])
    else:
        wall = None
    return {"in": name, **({"wall_mm": round(float(wall), 2)} if wall is not None else {})}


def as_drawn_ceiling(drawn: Optional[dict], governs: str, safety: Optional[float], pl: Optional[dict]):
    """Rule 6 (#228 review): a carve takes material away, so no step reads stronger than the plywood did as drawn. A step that carves under a
    held edge loses the plate check and falls back to the FEA, which reads a plywood top high: the as-drawn plate's number across the grain,
    the one it's judged by, is its ceiling. It's an upper bound, not the step's number (a plate held on three edges is weaker than on four), so
    the plate is marked ``as_drawn`` and the step reads "no higher than" it. Returns ``(governs, safety, plate)``."""
    if drawn and safety is not None and safety > drawn["safety_across"]:
        return "plate", drawn["safety_across"], {**drawn, "as_drawn": True}
    return governs, safety, pl


def check_load(ctx: dict, i: int, min_safety: float, solid=None):
    """One load through the FEA (on ``solid``, the part's voxels unless given) and the plate check.
    Returns ``(case, result)``; the case is the record's entry for it."""
    from scipy import ndimage

    ls, load, box, mat = ctx["ls"], ctx["loads"][i], ctx["boxes"][i], ctx["mat"]
    ls.loads = []
    ls.load(tuple(float(v) * load["factor"] for v in load["force"]), box=box)
    r = ls.solver().solve(ls.solid if solid is None else solid)
    case = {"name": load["name"], "lb": load["lb"], "factor": load["factor"],
            "force_n": [round(v, 1) for v in load["force"]], "lo": load["lo"], "hi": load["hi"]}
    if not r.supported:
        case.update({"holds": False, "safety": 0.0, "governs": "fea", "fea": {"supported": False},
                     "why": "nothing connects where it's pushed to where it's held"})
        return case, r
    # judged beside, not at, where loads and supports attach: a voxel model's stress there is the mesh's
    near = ndimage.binary_dilation(ctx["attach"], iterations=1)
    judged = r.solid & ~near
    if judged.sum() < 20:
        judged = r.solid
    vm = np.where(judged, r.von_mises, 0.0)
    strength = ctx.get("strength_map")
    worked = vm / strength if strength is not None else vm / mat["strength"]   # each voxel by its own (CALI-82)
    hot = np.unravel_index(int(np.argmax(worked)), vm.shape)
    at = np.asarray(ls.grid.origin) + ls.grid.spacing * np.asarray(hot)
    peak = float(vm[hot])
    fea = {"supported": True, "peak_mpa": round(peak, 2), "robust_mpa": round(float(r.peak_stress), 2),
           "safety": fea_safety(float(worked[hot])),
           "deflection_mm": round(float(r.max_displacement), 3),
           "at": [round(float(x), 1) for x in at], **_peak_in(ctx, at, ls.grid.spacing)}
    pl = plate_check(ctx["pieces"], load, ctx.get("plate_mat") or mat, ctx["tol"],
                     under=with_held(ctx.get("under"), ctx.get("held") or [], ctx["tol"]))
    options = [("fea", fea["safety"])]
    if pl and pl.get("done"):
        options.append(("plate", pl["safety_across"]))
    governs, safety = min(((k, s) for k, s in options if s is not None), key=lambda x: x[1],
                          default=("fea", None))
    governs, safety, pl = as_drawn_ceiling((ctx.get("plate_ceiling") or {}).get(i), governs, safety, pl)
    # a wall the load runs down can fold before it crushes (CALI-159, #229): the hand check governs where it's the lowest.
    # What it took over from is kept, so an FEA too coarse to see the wall still says so (no verdict greener)
    from . import buckling as B

    folds = [{**r, "safety": V.cut(r["safety"])} if r["done"] else r
             for r in B.check(ctx["pieces"], load, ctx.get("plate_mat") or mat, ctx["tol"])]
    weakest = B.governing(folds)
    if weakest is not None and (safety is None or weakest["safety"] < safety):
        case["over"] = governs
        governs, safety = "buckling", weakest["safety"]
    if folds:
        case["buckling"] = folds
    case.update({"fea": fea, "plate": pl, "safety": safety, "governs": governs,
                 "holds": bool(safety is not None and safety >= min_safety),  # producer
                 # where it's predicted to break, placed the same way: linear to failure, as wood is
                 # close to; the joints aren't modelled and may go first
                 "breaks_lb": V.cut_lb(load["lb"] * load["factor"] * safety) if safety else None,   # cut (#214)
                 # does it bend between where it's held? An FEA alone can't settle that (CALI-153)
                 **({"spans": spans_between(ctx["patches"], load["lo"], load["hi"], load["force"], ls.grid.spacing)}
                    if "patches" in ctx else {})})
    if any(pc.get("holes") for pc in ctx["pieces"] if pc["kind"] == "sheet"):
        from .lighten import judge_holed       # a panel stood on with holes: not by the plate formula (CALI-73)

        case = judge_holed(ctx, i, case, r, min_safety)
    return case, r


#: What a printed verdict's number rests on, said beside the promise (CALI-86, #71 rework).
ROUGH = ("Printed parts are a rough model: the plastic's share at half its strength across the layers, on the safe "
         "side, until a printed test piece loaded to breaking says otherwise.")


def rough(run: dict, case: dict) -> bool:
    """Whether a verdict rests on the printed model: the part's printed, and the plywood's plate check doesn't govern
    this case (a plywood top on printed sides that fails as a beam is plywood's verdict)."""
    return bool((run.get("material") or {}).get("printed")) and case.get("governs") != "plate"


NOTES = [
    "The FEA takes the joints as solid wood and its panel edges come out partly clamped, so it reads "
    "stiffer than glued-and-screwed; the plate check frees the edges, the safe side. Neither checks the "
    "glue or the screws.",
    "“Breaks at” is the load, placed the same way, at which the governing check reaches the material's "
    "strength: a prediction to test, not a rating.",
]


#: What a run on a solid with more in it than its pieces says (#209 review): with a piece missing from construction(), the solid may be the part as built.
FILLED_NOTE = ("This ran on a solid with more in it than its pieces: its shape filled in, or a piece missing from its construction. Its numbers "
               "are that solid's.")

#: what a check says where it gave no result that can be read
NO_RESULT = {"unchecked": "not checked: its walls are too thin for the voxels",
             "span": "not settled: the check holds its ends fixed",
             "unresolved": "not resolved yet: check it again finer",
             "untrusted": "not trusted: it ran on a solid with more in it than its pieces"}


def done_words(n: int, v: dict, worst: Optional[float]) -> str:
    """The last line of a check. A number only beside a result: where the card withholds it, so does this (#178 review)."""
    said = {"holds": "it holds", "fails": "it doesn't hold", **NO_RESULT}.get(v["kind"], v["word"])
    return f"{n} load(s) checked: " + said + (f", {worst:g}x" if worst and v["kind"] not in NO_RESULT else "")


@one_at_a_time
def study(store: DesignStore, part_id: str, *, min_safety: float = MIN_SAFETY,
          emit: Optional[Callable] = None, spacing: Optional[float] = None,
          stop: Optional[Callable[[], None]] = None) -> dict:      # ``stop``: cancels while it waits its turn (#169)
    """Every load the part declares, through whittle's FEA and the plate check. Returns the run record."""
    emit = emit or (lambda *a, **k: None)
    t0 = time.time()
    try:
        ctx = prepare(store, part_id, emit, spacing=spacing)
    except ValueError as e:
        # kept, so the card says why rather than offering a check that fails the same way (CALI-81)
        store.append_history(part_id, {"kind": "load", "action": "failed", "why": str(e),
                                       "version": store.design.part(part_id).version})
        raise
    loads, mat, held = ctx["loads"], ctx["mat"], ctx["held"]

    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out_dir = os.path.join(runs_dir(store), rid)
    os.makedirs(out_dir, exist_ok=True)
    cases = []
    t1 = time.time()                                  # the FEA's own time, for the finer run's estimate (CALI-97)
    for i, load in enumerate(loads):
        emit("case", f"{load['name']}: {load['lb']:g} lb × {load['factor']:g}", progress=i / len(loads))
        case, r = check_load(ctx, i, min_safety)
        if r.supported:
            with open(os.path.join(out_dir, f"case_{i:02d}.json"), "w") as f:
                json.dump(heat_mesh(ctx["mesh"], ctx["ls"].grid, r.von_mises, r.solid, 2 * ctx["spacing"]), f)
            case["heat"] = f"case_{i:02d}.json"
        cases.append(case)

    fea_seconds = time.time() - t1
    notes = [f"{mat['name']}: E {mat['E']:g} MPa, strength {mat['strength']:g} MPa — {mat['basis']}.", *NOTES,
             *buckling_notes(ctx["pieces"], loads, mat, ctx["tol"], ctx.get("plate_mat"))]
    if mat.get("note"):
        notes.append(mat["note"])
    if ctx.get("note"):
        notes.append(ctx["note"])
    if ctx["coarse"]:
        notes.append(ctx["coarse"])
    if any(h.get("default") for h in held):
        notes.append("Held by the floor: everything at its underside, as if it stands on a flat floor.")
    worst = run_safety(cases)            # from the cases that ran, never 0x (#140 review)
    record = {
        "id": rid, "part": part_id, "kind": "load", "created": time.time(),
        "version": store.design.part(part_id).version, "seconds": round(time.time() - t0, 1),
        "material": mat, "spacing_mm": round(ctx["spacing"], 2), "voxels": int(ctx["ls"].solid.sum()),
        "min_safety": min_safety, "held": held, "cases": cases, "notes": notes,
        "cut": True,                  # its numbers are kept cut toward safe (CALI-152): one on its limit is settled
        "safety": worst, "holds": bool(cases) and all(c.get("holds") for c in cases),  # producer
    }
    thin = ctx.get("thinnest")
    if thin:                                          # can the FEA see its thinnest wall? (CALI-97)
        record["thinnest_mm"] = round(thin, 2)
        if ctx.get("thinnest_where"):
            record["thinnest_where"] = ctx["thinnest_where"]
        record["unseen"] = unseen_walls(ctx.get("found") or [], ctx["spacing"])     # every one, any material (#248 review)
        record["across"] = round(thin / ctx["spacing"], 3)
        record["resolved"] = _sees(thin / ctx["spacing"])
        if not record["resolved"]:
            seen = (f"The FEA ran at {ctx['spacing']:.2g} mm voxels across a {thin:.2g} mm wall: too coarse to see "
                    f"it (it takes {RESOLVE_MIN:g} across).")
            want = math.floor(thin / RESOLVE_MIN * 100) / 100
            if want >= ctx["finest"]:
                # a run whose voxels don't connect the load to a support stops at once: its time says nothing about
                # a run that does (the bar stool: "about 1 min" for 39). Then no estimate, said so (#100 review)
                joined = all((c.get("fea") or {}).get("supported") for c in cases)
                minutes = finer_minutes(record["voxels"], ctx["spacing"], want, fea_seconds,
                                        record["seconds"] - fea_seconds) if joined else None
                record["finer"] = {"spacing_mm": want, "minutes": minutes}
                notes.append(f"{seen} Check it again at {want:g} mm" + (f" (about {minutes} min)." if minutes else
                             ": how long it takes can't be told from this run, whose voxels didn't connect the "
                             "load to a support."))
            else:
                record["too_thin"] = True
                record["sees_mm"] = round(RESOLVE_MIN * ctx["finest"], 1)      # the wall the check can see, at this size
                if ctx.get("thin_said"):                  # where, and what to change (#136 review)
                    record["thin_said"] = ctx["thin_said"]
                notes.append(f"{seen} {RESOLVE_MIN:g} across would take more voxels than a study of a part this "
                             f"size may: {NOT_CHECKED}")
    from .consistency import filled

    if filled(store, part_id):                        # what this number rests on (CALI-96)
        record["filled"] = True
        notes.append(FILLED_NOTE)
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump(record, f, indent=2, default=str)
    from . import verdicts

    from .consistency import bare_edge

    # one verdict (CALI-112): the history line and the message say it; loaded in the middle only (CALI-94) too
    v = verdicts.run(record, edge=bool(bare_edge(store, part_id)))
    store.append_history(part_id, {"kind": "load", "action": "studied", "run": rid,
                                   "cases": len(cases), "safety": worst,
                                   "holds": record["holds"],  # producer: the study's number, kept for older readers
                                   "verdict": {k: x for k, x in v.items() if k != "cases"},
                                   # the history line says "not resolved", never "holds", for it (CALI-110)
                                   **({"unresolved": True} if v["kind"] in ("unresolved", "unchecked") else {}),
                                   **({"middle_only": True} if v["kind"] == "edge" else {})})
    store.append_log({"kind": "load", "action": "studied", "part": part_id, "run": rid})
    emit("done", done_words(len(cases), v, worst), run=rid, progress=1.0)
    return record


def finer_minutes(voxels: int, spacing: float, finer: float, fea_seconds: float, setup_seconds: float) -> int:
    """About how long a run at ``finer`` mm takes, from this run's own time per voxel (CALI-97, #100 item 10).

    A finer grid has (spacing / finer)³ the voxels, and each takes longer: the solver's iterations grow with the grid
    (measured on the tube and the box stool, time per voxel went as about the cube root of the voxel count). So the
    FEA's time goes as the voxels to the 4/3. A guess from one run, said as "about"."""
    more = (spacing / finer) ** 3
    return max(1, round((setup_seconds + fea_seconds * more ** (4 / 3)) / 60))


def default_check(store: DesignStore, part_id: str) -> Optional[dict]:
    """The strength check a carve or a lightening goes by: this version's at the default voxels, the ones a carve runs
    at. A finer run asked for (CALI-97) is always finer than the default, so it's the coarsest at this version (the
    newest of those), never just the latest. None when this version has no check."""
    entry = store.design.part(part_id)
    runs = [r for r in list_runs(store, part_id) if entry and r.get("version") == entry.version]
    return max(runs, key=lambda r: r.get("spacing_mm") or 0) if runs else None     # max keeps the first: the newest


#: what's said where the check saw no stress at all (#202), and why it can't: the two things to look at
NO_STRESS = ("the check couldn't see any stress in this part at this size, so a carve has nothing to go by: the piece under the load may be "
             "too thin for its voxels, the load's patch may be smaller than the voxels, or the load may go straight into what holds it. "
             "Look at where the load sits, how big it is and how thick the part is there")
#: the same, on the card, in place of a verdict
BLIND = ("Not resolved: the check couldn't see any stress in this part at this size. The piece under the load may be too thin for its voxels, "
         "the load's patch may be smaller than the voxels, or the load may go straight into what holds it. Look at where the load sits, how "
         "big it is and how thick the part is there.")


def blocked(store: DesignStore, part_id: str) -> Optional[dict]:
    """What stops a carve or a lightening before it starts, from its default check (#144 review: the card offered Carve
    on the bar stool while the Carve button refused it). The one test the Carve button, the Lighten button and the
    card's carve offer all read, so they can't disagree; the studies themselves refuse on the same ``already_fails``.
    ``{"why": "already_fails" | "too_thin" | "unsupported" | "unchecked", "carve": words, "lighten": words or ""}``, or
    None. ``unchecked``: no strength check of this version (#144, on Theo's own stool, whose v7 has none): the card
    offered Carve and the button was live until the carve's own resolution check refused the click."""
    fails = already_fails(store, part_id)        # carving only takes material away (#137 item 3)
    if fails:
        return {"why": "already_fails", "carve": f"{fails}, then carve",
                "lighten": f"{fails[:1].upper()}{fails[1:]}, then lighten it"}
    rec = default_check(store, part_id)
    if rec is None:                              # what it holds, how thin its walls, how long a carve: all from it
        return {"why": "unchecked", "carve": "Check it holds first: a carve starts from its strength check",
                "lighten": ""}               # a lightening's holes are checked as it goes, by hand checks too
    if rec.get("too_thin"):                      # none a study may make can see its walls (#101, #136)
        said = rec.get("thin_said")
        return {"why": "too_thin",
                "carve": f"Can't carve it by strength: {said}" if said else
                "Its walls are too thin for the voxel check at this size, so it can't be carved by strength",
                "lighten": f"Can't lighten it by strength: {said}" if said else
                "Its walls are too thin for the voxel check at this size, so it can't be lightened by strength"}
    if any((c.get("fea") or {}).get("supported") is False for c in rec.get("cases") or []):
        return {"why": "unsupported", "carve": "its voxels don't connect the load to a support yet, so a carve can't run",
                "lighten": ""}               # a lightening's holes are checked by the hand checks too
    if rec.get("cases") and all(blind(rec, c) for c in rec["cases"]):     # #202: one case that read stress is enough to carve by
        return {"why": "no_stress", "carve": NO_STRESS, "lighten": ""}
    return None


def already_fails(store: DesignStore, part_id: str) -> Optional[str]:
    """Why a carve or a lightening won't start: this version's own strength check already fails (#137 item 3: Carve
    was offered and run on the bar stool at 0.53x; carving only takes material away). In words, "it already fails
    (0.53x, in the cone around z 15.3 in): make it hold first", or None."""
    from . import verdicts
    from .answers import _times, worst_at

    rec = default_check(store, part_id)
    if rec is None:
        return None
    v = verdicts.run(rec)
    if v["kind"] != "fails":
        return None
    worst = min((c for c in rec.get("cases") or [] if c.get("safety") is not None), key=lambda c: c["safety"],
                default=None)
    where, _ = worst_at(rec, worst, store.design.display_units == "in") if worst else ("", None)
    times = _times(rec["safety"], need=rec.get("min_safety")) if rec.get("safety") is not None else "as checked"
    if v.get("coarse") or (worst is not None and unresolved(rec, worst)):      # as the strength line says it (#139)
        return (f"its check says it fails ({times}, a coarse run: the fail may be the model's"
                + (f"; {where}" if where else "") + "): make it hold first")
    return f"it already fails ({times}" + (f", {where}" if where else "") + "): make it hold first"


def list_runs(store: DesignStore, part_id: Optional[str] = None) -> list[dict]:
    root = runs_dir(store)
    if not os.path.isdir(root):
        return []
    out = []
    for rid in sorted(os.listdir(root), reverse=True):
        rec = load_run(store, rid)
        if rec and (part_id is None or rec.get("part") == part_id):
            out.append(rec)
    return newest_first(out)          # made last first, not by id (CALI-97)


def load_run(store: DesignStore, rid: str) -> Optional[dict]:
    if not rid or "/" in rid or ".." in rid:
        return None
    path = os.path.join(runs_dir(store), rid, "run.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def heat_path(store: DesignStore, rid: str, index: int) -> str:
    if not rid or "/" in rid or ".." in rid:
        raise ValueError("bad run id")
    return os.path.join(runs_dir(store), rid, f"case_{int(index):02d}.json")
