"""CALI-183 (#294, Theo's addition): Copy… and Move…, a part placed by a typed form.

Theo, 2026-11-14: "maybe a copy and move or specify a location to put the copy on". A part's place is its pose in
``assembly.yaml`` (``position`` in mm, ``rotation`` in degrees, three.js XYZ), which every check already builds it at
(:func:`measure.pose_matrix`). **Move** writes that pose. **Copy** writes a new part from the part's own script, independent
of it (no mirror, no FOLLOWS), and places it the same way. Both are measured afterwards against every other part, and an
overlap or a touch is said.

Where it goes, one of:
- ``offset``: ``[dx, dy, dz]`` mm from where it is;
- ``at``: ``[x, y, z]`` mm, where the middle of its bounding box goes;
- ``beside``: ``{"part", "side"}``, touching that part's box on ``side`` (``+x`` … ``-z``); the other two directions stay.

And ``turn``: ``{"axis": "x"|"y"|"z", "deg": 0|90|180|270}``, about the part's own middle, so it turns in place before
it's placed. Numbers are mm here; the page converts from the design's units.
"""

from __future__ import annotations

import math
import os
import re
import shutil
from typing import Optional

import numpy as np

#: a side of a part's box: (axis index, which way)
SIDES = {"+x": (0, 1), "-x": (0, -1), "+y": (1, 1), "-y": (1, -1), "+z": (2, 1), "-z": (2, -1)}
TURNS = (0, 90, 180, 270)
#: further than this from the origin, a number is a typo, not a place (mm: 100 m)
FAR = 100_000.0
#: closer than this, two parts touch (mm); an overlap smaller than this is the mesh's, not a collision (mm³)
TOUCH_MM = 0.5
OVERLAP_MM3 = 1.0


def pose(store, pid: str) -> dict:
    """``{"position", "rotation"}`` of a part as it sits in the design."""
    part = _entry(store, pid)
    return {"position": [float(v) for v in part.position], "rotation": [float(v) for v in part.rotation]}


def _entry(store, pid: str):
    part = next((p for p in store.assembly.parts if p.id == pid), None)
    if part is None:
        raise KeyError(pid)
    return part


def _rot(deg) -> np.ndarray:
    from . import measure

    return measure.pose_matrix(None, deg)[:3, :3]


def _euler(m: np.ndarray) -> list[float]:
    from scipy.spatial.transform import Rotation

    out = Rotation.from_matrix(m).as_euler("XYZ", degrees=True)
    return [_clean(v) for v in out]


def _clean(v: float) -> float:
    """A number as it's kept: a whole one where it's within a hair of one (a quarter turn is 90, not 89.99999999)."""
    r = round(float(v))
    v = float(r) if abs(v - r) < 1e-6 else round(float(v), 6)
    return 0.0 if v == 0 else v


def _numbers(name: str, v) -> list[float]:
    try:
        out = [float(x) for x in v]
    except (TypeError, ValueError):
        raise ValueError(f"{name} is three numbers: x, y and z")
    if len(out) != 3 or not all(math.isfinite(x) for x in out):
        raise ValueError(f"{name} is three numbers: x, y and z")
    if any(abs(x) > FAR for x in out):
        raise ValueError(f"{name} is more than 100 m away: is a number mistyped?")
    return out


def _turn(turn) -> Optional[np.ndarray]:
    if not turn:
        return None
    axis, deg = (turn.get("axis") or "z").lower(), turn.get("deg", 0)
    if axis not in ("x", "y", "z"):
        raise ValueError("a turn is about x, y or z")
    try:
        deg = int(deg)
    except (TypeError, ValueError):
        raise ValueError("a turn is 0, 90, 180 or 270 degrees")
    if deg not in TURNS:
        raise ValueError("a turn is 0, 90, 180 or 270 degrees")
    if deg == 0:
        return None
    angles = [0.0, 0.0, 0.0]
    angles["xyz".index(axis)] = float(deg)
    return _rot(angles)


def placed(store, pid: str, how: dict, original: Optional[str] = None) -> dict:
    """The pose ``how`` puts the part at: ``{"position", "rotation"}``. ValueError with why, for a placement that can't
    be (a bad number, a part that isn't there, nothing to do). ``original``: for a copy, the part it's a copy of, which it
    may go beside."""
    how = how or {}
    ways = [k for k in ("offset", "at", "beside") if how.get(k) is not None]
    if len(ways) > 1:
        raise ValueError("say one of where: an offset, exact coordinates, or beside a part")
    turn = _turn(how.get("turn"))
    if not ways and turn is None:
        raise ValueError("that leaves it where it is: give an offset, coordinates, a part to go beside, or a turn")

    was = pose(store, pid)
    world = store.part_geometry(pid).require_mesh()
    old = _rot(was["rotation"])
    lo, hi = world.bounds
    middle = (lo + hi) / 2.0
    # the part in its own frame, turned as it'll be: its box, and where its middle falls
    local = world.vertices - np.asarray(was["position"])
    local = local @ np.linalg.inv(old).T
    rot = (turn @ old) if turn is not None else old
    turned = local @ rot.T
    tlo, thi = turned.min(axis=0), turned.max(axis=0)
    position = middle - (tlo + thi) / 2.0                # turned in place: its middle stays where it was
    box = (tlo + position, thi + position)

    if how.get("offset") is not None:
        position = position + np.asarray(_numbers("an offset", how["offset"]))
    elif how.get("at") is not None:
        position = position + (np.asarray(_numbers("where it goes", how["at"])) - middle)
    elif how.get("beside") is not None:
        b = how["beside"] or {}
        other, side = b.get("part"), (b.get("side") or "").lower()
        if side not in SIDES:
            raise ValueError("beside a part is on one of its sides: +x, -x, +y, -y, +z or -z")
        if other == pid and original is None:
            raise ValueError("a part can't go beside itself")
        if store.design.part(other) is None:
            raise ValueError(f"there's no part {other!r} to put it beside")
        olo, ohi = store.part_geometry(other).require_mesh().bounds
        i, way = SIDES[side]
        shift = (ohi[i] - box[0][i]) if way > 0 else (olo[i] - box[1][i])
        position = position.copy()
        position[i] += shift
    return {"position": [_clean(v) for v in position], "rotation": _euler(rot)}


def described(how: dict, units: str = "mm") -> str:
    """Where a placement puts it, in a person's words, in the design's units."""
    def n(mm):
        if units == "in":
            return f"{mm / 25.4:g} in"
        return f"{mm:g} mm"

    bits = []
    if how.get("offset") is not None:
        d = _numbers("an offset", how["offset"])
        bits.append(", ".join(f"{n(v)} along {a}" for a, v in zip("xyz", d) if v) or "where it was")
    elif how.get("at") is not None:
        p = _numbers("where it goes", how["at"])
        bits.append(f"its middle at x {n(p[0])}, y {n(p[1])}, z {n(p[2])}")
    elif how.get("beside") is not None:
        b = how["beside"]
        bits.append(f"beside {b['part']} on its {b['side']} side")
    t = how.get("turn") or {}
    if t and int(t.get("deg") or 0):
        bits.append(f"turned {int(t['deg'])}° about {t.get('axis', 'z')}")
    return ", ".join(bits)


def refuse_mirrored(store, pid: str, what: str) -> None:
    """A mirror and its source are placed by the mirror's plane: moving either alone would quietly break it."""
    from . import mirror

    source = mirror.source_of(store, pid)
    if source:
        raise ValueError(f"I can't {what} {pid} on its own: it mirrors {source}, so it sits where {source}'s mirror "
                         f"puts it. Move {source}, or break the mirror first")
    by = mirror.mirrors_of(store, pid)
    if by:
        raise ValueError(f"I can't {what} {pid} on its own: {', '.join(by)} mirrors it, and wouldn't follow. Break the "
                         f"mirror first")


def set_pose(store, pid: str, to: dict, *, said: str, action: str = "move") -> dict:
    """Put a part at ``to``, kept in its history with where it was, so Put it back can return it there."""
    part = _entry(store, pid)
    was = pose(store, pid)
    part.position = [_clean(v) for v in _numbers("its position", to["position"])]
    part.rotation = [_clean(v) for v in _numbers("its rotation", to["rotation"])]
    store.save()
    store.append_history(pid, {"kind": "pose", "action": action, "from": was, "to": pose(store, pid), "said": said})
    if any(s.get("source") == "measured" and s.get("of") == pid for s in store.design.skeleton or []):
        from . import skeleton                     # a size measured off this part, measured again, as a revision does

        skeleton.remeasure(store, pid)
    return was


def move(store, pid: str, how: dict, units: str = "mm") -> dict:
    """Move… : the part at the placement's pose. ``{"from", "to", "said", "near"}``."""
    if store.design.part(pid) is None:
        raise KeyError(pid)
    refuse_mirrored(store, pid, "move")
    to = placed(store, pid, how)
    if to == pose(store, pid):
        raise ValueError("that leaves it where it is: give an offset, coordinates, a part to go beside, or a turn")
    where = described(how, units)
    was = set_pose(store, pid, to, said=where)
    near = measured(store, pid)
    return {"from": was, "to": to, "near": near, "said": f"Moved {pid}: {where}." + said_near(pid, near)}


# --- Copy… ----------------------------------------------------------------------------------------------------------------
_FOLLOWS = re.compile(r"^FOLLOWS\s*=")


def own_script(text: str) -> str:
    """A part's script as a copy's: a mirror's made its own, as Break the mirror makes it, and no FOLLOWS (its numbers stay
    as they are now, and follow nothing)."""
    import ast

    from . import mirror

    got = mirror.of(text)
    if got is not None:
        text = mirror._OF.sub(f"MIRROR_OF = None  # was a mirror of {got['source']}: its own script now", text, count=1)
        text = text.replace(mirror.HEAD.format(source=got["source"]),
                            f"# --- a copy of {got['source']}, mirrored: its own now ---", 1)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    lines = text.splitlines(keepends=True)
    for node in reversed(tree.body):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "FOLLOWS"):
            lines[node.lineno - 1:node.end_lineno] = ["FOLLOWS = {}  # a copy: its numbers are its own\n"]
    return "".join(lines)


def free_id(store, pid: str) -> str:
    """``side_left_2``, or the next number free (a part in the trash keeps its id taken)."""
    base = re.sub(r"_\d+$", "", pid) or pid
    taken = {p.id for p in store.design.parts} | {p.id for p in store.assembly.parts}
    from . import trash

    if os.path.isdir(trash.root(store)):           # a part in the trash can be put back: its id stays taken
        taken |= {re.sub(r"-\d{8}-\d{6}x*$", "", n) for n in os.listdir(trash.root(store))}
    for i in range(2, 1000):
        cand = f"{base}_{i}"
        if cand not in taken and not os.path.exists(store.part_dir(cand)):
            return cand
    raise ValueError(f"no free name for a copy of {pid}")


def copy(store, pid: str, how: Optional[dict] = None, units: str = "mm") -> dict:
    """Copy… : a new part from ``pid``'s script (and spec, loads as edited, grain and piece names), independent of it, at
    the placement (or where it is, then said to be overlapping). ``{"part", "to", "said", "near"}``."""
    entry = store.design.part(pid)
    if entry is None:
        raise KeyError(pid)
    if not entry.version:
        raise ValueError(f"{pid} isn't built yet: there's nothing to copy")
    how = dict(how or {})
    if not any(how.get(k) is not None for k in ("offset", "at", "beside")):
        how["beside"] = {"part": pid, "side": "+x"}   # nothing said: beside the original, never inside it
    to = placed(store, pid, how, original=pid)     # worked out before the copy exists: a bad placement writes nothing
    new = free_id(store, pid)
    src = _entry(store, pid)
    for book in ("scenarios", "grain", "piece_labels"):
        kept = (getattr(store.design, book) or {}).get(pid)
        if kept:
            import copy as _copy

            getattr(store.design, book)[new] = _copy.deepcopy(kept)
    feedback = f"a copy of {pid}"
    if store.is_scripted(pid):
        text = own_script(store.read_script(pid))
        from .assembly import carved_file

        name = carved_file(text)
        if name:                                   # its carved shape goes with it, or the copy wouldn't build
            here = os.path.join(store.part_dir(pid), "carved", os.path.basename(name))
            if os.path.exists(here):
                os.makedirs(os.path.join(store.part_dir(new), "carved"), exist_ok=True)
                shutil.copy2(here, os.path.join(store.part_dir(new), "carved", os.path.basename(name)))
        store.write_part(new, text, intent=entry.intent, spec=store.read_spec(pid), feedback=feedback, action="copy",
                         extra={"copied_from": pid, "of_version": entry.version})
    else:
        if not os.path.exists(store.mesh_path(pid)):   # an imported reference read from elsewhere: nothing here to copy
            raise ValueError(f"{pid}'s shape isn't kept in the design, so there's nothing to copy")
        with open(store.mesh_path(pid), "rb") as f:
            store.write_mesh_part(new, f.read(), origin=entry.origin, action="copy", feedback=feedback,
                                  extra={"copied_from": pid, "of_version": entry.version})
    if entry.label:                                # a named part's copy is named too: "Step stool 2" (renameable)
        store.design.part(new).label = f"{entry.label} {new.rsplit('_', 1)[-1]}"
    made = _entry(store, new)
    made.role = src.role
    made.position, made.rotation = list(to["position"]), list(to["rotation"])
    store.save()
    from . import tree

    lay = tree.layout(store)                       # in the tree beside its original, at its level
    order = [x for x in lay["order"] if x != new]
    order.insert(order.index(pid) + 1, new)
    parent = dict(lay["parent"])
    if parent.get(pid):
        parent[new] = parent[pid]
    tree.set_layout(store, order, parent)
    near = measured(store, new)
    where = described(how, units)
    said = (f"Copied {pid} as {new}, {where}. It's a part of its own: "
            f"say \"make {new} a mirror of {pid}\" or \"{new} follows {pid}'s sizes\" to link them." + said_near(new, near))
    return {"part": new, "to": to, "near": near, "said": said}


# --- measured afterwards ----------------------------------------------------------------------------------------------
def measured(store, pid: str) -> list[dict]:
    """What the part overlaps or touches where it now sits: ``[{"part", "kind": "overlap"|"touch"|"unmeasured", "said",
    "mm3"?}]``. Mesh against mesh, every other built part; a part that won't build is said as not measured."""
    from . import measure

    out = []
    try:
        me = store.part_geometry(pid)
    except Exception as e:  # noqa: BLE001 — said, never as measured
        return [{"part": pid, "kind": "unmeasured", "said": f"{pid} won't build to be measured: {e}"}]
    mine = me.require_mesh()
    for p in store.design.parts:
        if p.id == pid or not p.version:
            continue
        try:
            g = store.part_geometry(p.id)
            other = g.require_mesh()
            if not measure._aabb_overlap(mine, other, pad=TOUCH_MM):
                continue
            vol = measure.interference(me, g)
            if vol > OVERLAP_MM3:
                out.append({"part": p.id, "kind": "overlap", "mm3": round(vol, 1),
                            "said": f"it overlaps {p.id} by {vol / 1000:.1f} cm³"})
                continue
            gap = measure.min_clearance(me, g)
            if gap <= TOUCH_MM:
                out.append({"part": p.id, "kind": "touch", "said": f"it touches {p.id}"})
        except Exception as e:  # noqa: BLE001
            out.append({"part": p.id, "kind": "unmeasured", "said": f"whether it meets {p.id} wasn't measured ({e})"})
    return out


def said_near(pid: str, near: list[dict]) -> str:
    if not near:
        return " Measured where it sits: it doesn't touch or overlap another part."
    return " Measured where it sits: " + "; ".join(n["said"] for n in near) + "."
