"""CALI-109 (#109, slice a) — a part's faces and edges, each with an id, so a click can say exactly which.

Theo, after the bar stool's fillet went on the wrong edge: "perhaps in the UI i could select an edge or a face to further
clarify what I'm talking about?" An STL has lost which triangle belonged to which face, so each B-rep face is tessellated
as its own group and each edge sampled as a polyline, keyed by an id for that version. Each says what it is: its type,
centre, axis and radius where it has them, and for an edge its two faces and whether it's an inside or outside corner.

Everything is in design coordinates, as the viewport draws the part; ``local`` is the same centre in the script's own, for
the designer. A part with no B-rep (carved, whittled, imported) comes back ``{"mesh": true}``: a pick there is a point.
Worked out once per version and kept beside the part; only the newest is kept.
"""

from __future__ import annotations

import json
import os
import re
from fractions import Fraction
from typing import Optional

import numpy as np

from .design import OCCT, DesignStore

#: how finely a face is tessellated and an edge sampled for the page, in mm and radians: picking, not manufacturing
LINEAR = 0.4
ANGULAR = 0.35
EDGE_POINTS = 24
#: bumped when what's kept changes: an older file is worked out again
SCHEMA = 3
#: how far along a face to step to see which way it leaves an edge, mm
STEP = 0.05

_FACE_KIND = {"PLANE": "plane", "CYLINDER": "cylinder", "CONE": "cone", "SPHERE": "sphere", "TORUS": "torus"}
_EDGE_KIND = {"LINE": "line", "CIRCLE": "circle", "ELLIPSE": "ellipse"}


def _vec(v) -> list[float]:
    return [round(float(x), 3) for x in v]


def _apply(pose, point) -> np.ndarray:
    p = np.asarray(point, float)
    return p if pose is None else (pose @ np.array([*p, 1.0]))[:3]


def _turn(pose, direction) -> np.ndarray:
    d = np.asarray(direction, float)
    return d if pose is None else pose[:3, :3] @ d


def _surface(face) -> dict:
    """A face's axis and radius, where its kind of surface has them (in the script's frame)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface  # type: ignore
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Torus  # type: ignore

    s, out = BRepAdaptor_Surface(face.wrapped), {}
    if s.GetType() == GeomAbs_Plane:
        d, at = s.Plane().Axis().Direction(), s.Plane().Location()
        out.update(axis=(d.X(), d.Y(), d.Z()), at=(at.X(), at.Y(), at.Z()))
    elif s.GetType() == GeomAbs_Cylinder:
        c = s.Cylinder()
        d, at = c.Axis().Direction(), c.Location()
        out.update(axis=(d.X(), d.Y(), d.Z()), radius=c.Radius(), at=(at.X(), at.Y(), at.Z()))
    elif s.GetType() == GeomAbs_Cone:
        c = s.Cone()
        d, at = c.Axis().Direction(), c.Apex()
        out.update(axis=(d.X(), d.Y(), d.Z()), at=(at.X(), at.Y(), at.Z()), semi=c.SemiAngle())
    elif s.GetType() == GeomAbs_Torus:
        t = s.Torus()
        d, at = t.Axis().Direction(), t.Location()
        out.update(axis=(d.X(), d.Y(), d.Z()), minor=t.MinorRadius(),   # a round on a circular edge: its radius is the minor
                   major=t.MajorRadius(), at=(at.X(), at.Y(), at.Z()))
    return out


def _curve(edge) -> dict:
    """An edge's axis and radius, if it's a circle (in the script's frame)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve  # type: ignore
    from OCP.GeomAbs import GeomAbs_Circle  # type: ignore

    c = BRepAdaptor_Curve(edge.wrapped)
    if c.GetType() != GeomAbs_Circle:
        return {}
    circ = c.Circle()
    d, at = circ.Axis().Direction(), circ.Location()
    return {"axis": (d.X(), d.Y(), d.Z()), "radius": circ.Radius(), "centre": (at.X(), at.Y(), at.Z())}


def _distance(shape, point) -> float:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex  # type: ignore
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape  # type: ignore
    from OCP.gp import gp_Pnt  # type: ignore

    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*(float(x) for x in point))).Vertex()
    return BRepExtrema_DistShapeShape(shape.wrapped, v).Value()


def _into(face, point, tangent) -> Optional[np.ndarray]:
    """The direction from an edge's point across this face: square to the edge, in the face, on the side the face is."""
    import cadquery as cq

    n = np.array(face.normalAt(cq.Vector(*point)).toTuple())
    side = np.cross(tangent, n)
    norm = np.linalg.norm(side)
    if norm < 1e-9:
        return None
    side /= norm
    return side if _distance(face, point + STEP * side) < _distance(face, point - STEP * side) else -side


def _corner(edge, a, b) -> Optional[str]:
    """"inside" or "outside", from which way one face leaves the edge against the other's outward normal: an inside
    corner's face runs toward the side the other faces. None where they meet flush, or it can't be told."""
    import cadquery as cq

    mid = edge.positionAt(0.5)
    point, tangent = np.array(mid.toTuple()), np.array(edge.tangentAt(0.5).toTuple())
    across = _into(a, point, tangent)
    if across is None:
        return None
    other = np.array(b.normalAt(cq.Vector(*point)).toTuple())
    side = float(np.dot(across, other))
    return None if abs(side) < 1e-3 else ("inside" if side > 0 else "outside")


def of_solid(solid, pose=None) -> dict:
    """``{"faces": [...], "edges": [...]}`` for a B-rep solid (a Workplane or a Shape), placed by ``pose``."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE  # type: ignore
    from OCP.TopExp import TopExp  # type: ignore
    from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape  # type: ignore
    import cadquery as cq

    shape = solid.val() if hasattr(solid, "val") else solid
    if len(getattr(solid, "vals", lambda: [shape])()) > 1:
        shape = cq.Compound.makeCompound(solid.vals())
    pose = None if pose is None or np.allclose(pose, np.eye(4)) else np.asarray(pose, float)
    faces = shape.Faces()
    index = {}
    out_faces = []
    for i, f in enumerate(faces):
        fid = f"f{i}"
        index[f.hashCode()] = (fid, f)
        verts, tris = f.tessellate(LINEAR, ANGULAR)
        pts = np.array([_apply(pose, v.toTuple()) for v in verts], float)
        surf = _surface(f)
        c = np.array(f.Center().toTuple())
        row = {"id": fid, "type": _FACE_KIND.get(f.geomType(), "surface"), "centre": _vec(_apply(pose, c)), "local": _vec(c),
               "area": round(float(f.Area()), 2), "verts": [round(float(x), 2) for x in pts.ravel()],
               "tris": [int(x) for t in tris for x in t]}
        if "axis" in surf:
            row["axis"] = _vec(_turn(pose, surf["axis"]))
        if "radius" in surf:
            row["radius"] = round(surf["radius"], 3)
        if "minor" in surf:
            row["minor"] = round(surf["minor"], 3)
        if "major" in surf:
            row["major"] = round(surf["major"], 3)
        if "semi" in surf:
            row["semi"] = round(surf["semi"], 6)
        if f.geomType() == "CYLINDER" and len(verts):          # a hole's wall faces its axis; a post's faces away from it
            on = np.array(verts[0].toTuple())
            axis_d = np.asarray(surf["axis"], float)
            out_from_axis = (on - np.asarray(surf["at"], float))
            out_from_axis -= axis_d * float(np.dot(out_from_axis, axis_d))
            row["hollow"] = bool(float(np.dot(np.array(f.normalAt(verts[0]).toTuple()), out_from_axis)) < 0)
        if "at" in surf:
            row["at"] = _vec(_apply(pose, surf["at"]))
        out_faces.append(row)
    owners = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape.wrapped, TopAbs_EDGE, TopAbs_FACE, owners)
    out_edges = []
    for i, e in enumerate(shape.Edges()):
        beside = []
        if owners.Contains(e.wrapped):
            seen = set()
            for found in owners.FindFromKey(e.wrapped):
                face = cq.Face(found)
                h = face.hashCode()
                if h in index and h not in seen:
                    seen.add(h)
                    beside.append(index[h])
        pts = [_apply(pose, e.positionAt(t).toTuple()) for t in np.linspace(0, 1, EDGE_POINTS if e.geomType() != "LINE" else 2)]
        curve = _curve(e)
        mid = np.array(e.positionAt(0.5).toTuple())
        c = np.array(curve["centre"]) if "centre" in curve else mid
        # ``local`` is a point on the edge: what edge_at needs, and a ring's centre is on no edge at all (#177 review)
        row = {"id": f"e{i}", "type": _EDGE_KIND.get(e.geomType(), "curve"), "centre": _vec(_apply(pose, c)), "local": _vec(mid),
               "length": round(float(e.Length()), 2), "points": [_vec(p) for p in pts], "faces": [b[0] for b in beside],
               "corner": None}
        if "axis" in curve:
            row["axis"] = _vec(_turn(pose, curve["axis"]))
            row["radius"] = round(curve["radius"], 3)
        if len(beside) == 2:
            try:
                row["corner"] = _corner(e, beside[0][1], beside[1][1])
            except Exception:  # noqa: BLE001 — a corner it can't tell is left unsaid
                row["corner"] = None
        out_edges.append(row)
    return {"faces": out_faces, "edges": out_edges}


def _path(store: DesignStore, pid: str, version: int) -> str:
    return os.path.join(store.root, "parts", pid, f"features-v{version}.json")


def for_part(store: DesignStore, pid: str) -> dict:
    """A part's features at its current version, with where the part sits in the design. Raises ``KeyError`` for a part
    it hasn't got."""
    from . import measure

    entry = store.design.part(pid)
    if entry is None:
        raise KeyError(pid)
    placed = next((p for p in store.assembly.parts if p.id == pid), None)
    stamp = [list(placed.position or ()), list(placed.rotation or ())] if placed else []
    path = _path(store, pid, entry.version)
    try:
        with open(path) as f:
            got = json.load(f)
        if got.get("placed") == stamp and got.get("schema") == SCHEMA:
            return got
    except (OSError, ValueError):
        pass
    geometry = store.part_geometry(pid)
    if geometry.solid is None:
        out = {"mesh": True, "faces": [], "edges": []}
    else:
        pose = measure.pose_matrix(placed.position, placed.rotation) if placed else None
        with OCCT:
            out = {"mesh": False, **of_solid(geometry.solid, pose)}
    out.update(part=pid, version=entry.version, placed=stamp, schema=SCHEMA)
    folder = os.path.dirname(path)
    for old in os.listdir(folder):
        if old.startswith("features-v") and old.endswith(".json"):
            os.remove(os.path.join(folder, old))
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    os.replace(tmp, path)
    return out


def _length(mm: float, inches: bool) -> str:
    from .answers import _len

    return _len(mm, inches)


def with_words(features: dict, inches: bool) -> dict:
    """The features with what each is called, in the person's units, for the chip."""
    return {**features, "faces": [{**f, "said": said(features, "face", f["id"], inches)} for f in features.get("faces") or []],
            "edges": [{**e, "said": said(features, "edge", e["id"], inches)} for e in features.get("edges") or []]}


_FACE_WORD = {"plane": "flat face", "cylinder": "cylinder", "cone": "cone", "sphere": "sphere", "torus": "rounded face",
              "surface": "curved surface"}


def said(features: dict, kind: str, fid: str, inches: bool) -> Optional[str]:
    """What a picked feature is, in words and the person's units: "edge: the circle where the cone meets the flat face, 18
    in across, 14 mm up (inside corner)". None for an id this version hasn't got."""
    faces = {f["id"]: f for f in features.get("faces") or []}
    if kind == "face":
        f = faces.get(fid)
        if f is None:
            return None
        what = _FACE_WORD[f["type"]]
        size = f" {_length(2 * f['radius'], inches)} across" if f.get("radius") else ""
        return f"face: the {what}{size}, {_length(f['centre'][2], inches)} up"
    e = next((x for x in features.get("edges") or [] if x["id"] == fid), None)
    if e is None:
        return None
    meet = [_FACE_WORD[faces[x]["type"]] for x in e["faces"] if x in faces]
    where = f" where the {meet[0]} meets the {meet[1]}" if len(meet) == 2 and meet[0] != meet[1] else \
        f" between two {meet[0]}s" if len(meet) == 2 else ""
    size = f", {_length(2 * e['radius'], inches)} across" if e.get("radius") else \
        f", {_length(e['length'], inches)} long"
    corner = f" ({e['corner']} corner)" if e.get("corner") else ""
    return f"edge: the {e['type']}{where}{size}, {_length(e['centre'][2], inches)} up{corner}"


# --- did the change land on the pick (#109, slice c; #177 review) --------------------------------------------------------
# Three outcomes, and the default is "couldn't tell". Landed and missed each need positive evidence about the picked edge
# itself: not any new or moved face near it, and not some other ring that looks similar.
NOT_MEASURED = "I couldn't tell whether that landed on what you picked."
#: right place, wrong size: not a tick, and not a miss on location
PARTIAL = "partial"
UNDO = ' Say "roll it back" to undo it.'
_ASKED = re.compile(r"(\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)\s*(mm|cm|inch(?:es)?\b|in\b|\")", re.I)
#: how close two curves or surfaces must be to be the same one, mm: to the rounding they're kept at
SAME = 0.05
_TO_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, '"': 25.4}


def _asked_mm(text: str, word: str = "fillet|round") -> Optional[float]:
    """The length a request asks for, in mm: the one written nearest the word it's about ("a 3 mm fillet", "leave 20 mm of
    flat then fillet 3 mm"). None if it names none, or none that reads ("1/0 in")."""
    near = re.search(rf"\b({word})", text, re.I)
    found = list(_ASKED.finditer(text))
    if not found:
        return None
    at = near.end() if near else 0
    m = min(found, key=lambda x: min(abs(x.start() - at), abs(x.end() - near.start()) if near else 1e9))
    try:
        number = sum(float(Fraction(part)) for part in m.group(1).split())
    except (ValueError, ZeroDivisionError):
        return None
    unit = m.group(2).lower()
    return number * _TO_MM["in" if unit.startswith("inch") else unit]


def _size(mm: float, inches: bool) -> str:
    from .answers import _small_len

    return _small_len(mm, inches)


def _both(got: float, asked: float, inches: bool) -> tuple[str, str]:
    """Two sizes that differ, said so they read differently: "1/8 in, not 1/8 in" is no use, so those go in mm."""
    a, b = _size(got, inches), _size(asked, inches)
    return (a, b) if a != b else (f"{got:g} mm", f"{asked:g} mm")


def _parallel(a, b) -> bool:
    return abs(float(np.dot(np.asarray(a, float), np.asarray(b, float)))) > 0.9999


def _same_surface(a: dict, b: dict) -> bool:
    """The same surface, trimmed or not: the same plane, or the same cylinder, cone, torus or sphere. A spline has nothing
    to compare by, so it's never demonstrably the same."""
    if a["type"] != b["type"] or a["type"] not in ("plane", "cylinder", "cone", "torus", "sphere"):
        return False
    if "at" not in a or "at" not in b:
        return False
    gap = np.subtract(a["at"], b["at"])
    if a["type"] == "sphere":
        return abs(a.get("radius", 0) - b.get("radius", 0)) <= SAME and np.linalg.norm(gap) <= SAME
    if not _parallel(a["axis"], b["axis"]):
        return False
    axis = np.asarray(a["axis"], float)
    if a["type"] == "plane":
        return abs(float(np.dot(gap, axis))) <= SAME
    if a["type"] == "cylinder":
        return abs(a["radius"] - b["radius"]) <= SAME and np.linalg.norm(np.cross(gap, axis)) <= SAME
    if a["type"] == "cone":
        return abs(a["semi"] - b["semi"]) <= 1e-4 and np.linalg.norm(gap) <= SAME
    return abs(a["minor"] - b["minor"]) <= SAME and abs(a["major"] - b["major"]) <= SAME and np.linalg.norm(gap) <= SAME


def _same_curve(a: dict, b: dict) -> bool:
    if a["type"] != b["type"] or abs(a["length"] - b["length"]) > SAME:
        return False
    if a["type"] == "circle":
        return abs(a["radius"] - b["radius"]) <= SAME and np.linalg.norm(np.subtract(a["centre"], b["centre"])) <= SAME \
            and _parallel(a["axis"], b["axis"])
    p, q = np.asarray(a["points"], float), np.asarray(b["points"], float)
    if len(p) != len(q):
        return False
    return bool(np.abs(p - q).max() <= SAME or np.abs(p - q[::-1]).max() <= SAME)


def _faces_by_id(features: dict) -> dict:
    return {f["id"]: f for f in features["faces"]}


def _is_new(face: dict, before: dict) -> bool:
    return not any(_same_surface(face, b) for b in before["faces"])


def _on(face: dict, points: np.ndarray, reach: float) -> bool:
    """Every point within ``reach`` of the face's own triangles: the surface is where the edge was, all along it."""
    import trimesh

    from . import spatial

    mesh = trimesh.Trimesh(np.asarray(face["verts"], float).reshape(-1, 3), np.asarray(face["tris"], int).reshape(-1, 3),
                           process=False)
    _, gaps, _ = spatial.closest_point(mesh, points)
    return float(gaps.max()) <= reach


def _fillet(before: dict, after: dict, edge: dict, asked: Optional[float], inches: bool) -> tuple[str, Optional[bool]]:
    was, now = _faces_by_id(before), _faces_by_id(after)
    own = [was[i] for i in edge["faces"] if i in was]
    if len(own) != 2:
        return NOT_MEASURED, None
    same = [e for e in after["edges"] if _same_curve(edge, e)]
    for e in same:
        beside = [now[i] for i in e["faces"] if i in now]
        if len(beside) == 2 and all(any(_same_surface(f, g) for g in beside) for f in own):
            return "The edge you picked is still there, so the fillet didn't land on it." + UNDO, False
    if same:                                            # that curve's there, on faces it can't vouch for
        return NOT_MEASURED, None
    a, b = ([f["id"] for f in after["faces"] if _same_surface(side, f)] for side in own)
    if not a or not b:
        return NOT_MEASURED, None
    meets: dict = {}
    for e in after["edges"]:
        for i in e["faces"]:
            meets.setdefault(i, set()).update(x for x in e["faces"] if x != i)
    points = np.asarray(edge["points"], float)
    straight = edge["type"] == "line"
    along = points[-1] - points[0]
    for f in after["faces"]:
        if f["type"] not in ("cylinder", "torus", "surface") or not _is_new(f, before):
            continue
        # a straight edge's round is a cylinder along it, and a curved edge's is never a cylinder: a neighbour's round has its
        # end cap on these faces too, and on a short edge it's in reach from end to end (#177 review)
        if straight and (f["type"] != "cylinder" or not _parallel(f["axis"], along / np.linalg.norm(along))):
            continue
        if not straight and f["type"] == "cylinder":
            continue
        if not meets.get(f["id"], set()) & set(a) or not meets.get(f["id"], set()) & set(b):
            continue                                    # a round sits between the picked edge's own two faces
        r = f.get("minor") if f["type"] == "torus" else f.get("radius")
        if not _on(f, points, 3 * r + 0.5 if r else 0.5 * float(np.sqrt(f["area"]))):
            continue
        if r is None:
            return "Checked: there's a fillet on the edge you picked.", True
        if asked and abs(r - asked) > max(0.02 * asked, 0.05):
            got, want = _both(r, asked, inches)
            return f"It went on that edge, but it's {got} where you asked for {want}." + UNDO, PARTIAL
        return f"Checked: the fillet is on the edge you picked, {_size(r, inches)}.", True
    return NOT_MEASURED, None


def _hole(before: dict, after: dict, face: dict, asked: Optional[float], inches: bool) -> tuple[str, Optional[bool]]:
    if face["type"] != "plane":
        return NOT_MEASURED, None
    on_it = {f["id"] for f in after["faces"] if _same_surface(face, f)}
    was_there = {f["id"] for f in after["faces"] if not _is_new(f, before)}
    now = _faces_by_id(after)
    for f in after["faces"]:
        if f["type"] != "cylinder" or not f.get("hollow") or not _is_new(f, before):
            continue                                    # a post's wall faces away from its axis
        rims = [e for e in after["edges"] if f["id"] in e["faces"] and e["type"] == "circle"
                and abs(e["length"] - 2 * np.pi * f["radius"]) <= 0.02 * e["length"]]
        others = [next((x for x in e["faces"] if x != f["id"]), None) for e in rims]
        if len(rims) < 2 or not any(x in on_it for x in others):
            continue
        at = next(np.asarray(e["centre"], float) for e, x in zip(rims, others) if x in on_it)
        if not _on(face, at[None], 0.5):                # the picked face itself, not another pad on its plane
            continue
        if not all(x in was_there for x in others):     # a floor or a cap it made itself: blind, or a boss
            continue
        size = 2 * f["radius"]
        if asked and abs(size - asked) > max(0.02 * asked, 0.05):
            got, want = _both(size, asked, inches)
            return f"It went through that face, but it's {got} where you asked for {want}." + UNDO, PARTIAL
        return f"Checked: there's a {_size(size, inches)} hole through the face you picked.", True
    same = [now[i] for i in on_it]
    if any(abs(f["area"] - face["area"]) <= 0.001 * face["area"] and np.linalg.norm(np.subtract(f["centre"], face["centre"])) <= SAME
           for f in same):
        return "The face you picked has no new hole through it." + UNDO, False
    return NOT_MEASURED, None


def landed(before: Optional[dict], after: Optional[dict], pick: dict, message: str, inches: bool) -> dict:
    """Did a change asked of a picked edge or face land on it? ``{"said": one line, "landed": True, False, PARTIAL or
    None}``. None, "couldn't tell", is the default: landed and missed each need positive evidence about the pick itself.
    PARTIAL: on the right edge or face, at the wrong size."""
    said, hit = _landed(before, after, pick, message, inches)
    return {"said": said, "landed": hit}


def _landed(before, after, pick, message, inches) -> tuple[str, Optional[bool]]:
    if not before or not after or before.get("mesh") or after.get("mesh"):
        return NOT_MEASURED, None
    if pick.get("version") not in (None, before.get("version")):      # the ids are that version's
        return NOT_MEASURED, None
    words = (pick.get("text") or message or "").lower()
    kind, fid = pick.get("kind"), pick.get("id")
    if re.search(r"\b(remove|take off|delete|undo)\b", words) or "chamfer" in words:
        return NOT_MEASURED, None
    if kind == "edge" and re.search(r"\b(fillet|round)", words):
        edge = next((e for e in before["edges"] if e["id"] == fid), None)
        return _fillet(before, after, edge, _asked_mm(words), inches) if edge else (NOT_MEASURED, None)
    if kind == "face" and re.search(r"\bhole", words):
        face = next((f for f in before["faces"] if f["id"] == fid), None)
        return _hole(before, after, face, _asked_mm(words, "hole"), inches) if face else (NOT_MEASURED, None)
    return NOT_MEASURED, None
