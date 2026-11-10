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
        d = s.Plane().Axis().Direction()
        out["axis"] = (d.X(), d.Y(), d.Z())
    elif s.GetType() == GeomAbs_Cylinder:
        c = s.Cylinder()
        d = c.Axis().Direction()
        out.update(axis=(d.X(), d.Y(), d.Z()), radius=c.Radius())
    elif s.GetType() == GeomAbs_Cone:
        d = s.Cone().Axis().Direction()
        out["axis"] = (d.X(), d.Y(), d.Z())
    elif s.GetType() == GeomAbs_Torus:
        t = s.Torus()
        d = t.Axis().Direction()
        out.update(axis=(d.X(), d.Y(), d.Z()), minor=t.MinorRadius())   # a round on a circular edge: its radius is the minor
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
        row = {"id": f"e{i}", "type": _EDGE_KIND.get(e.geomType(), "curve"), "centre": _vec(_apply(pose, c)), "local": _vec(c),
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
        if got.get("placed") == stamp:
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
    out.update(part=pid, version=entry.version, placed=stamp)
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


# --- did the change land on the pick (#109, slice c) ------------------------------------------------------------------
_ASKED = re.compile(r"(\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)\s*(mm|inch(?:es)?\b|in\b|\")", re.I)
NOT_MEASURED = "I can't measure whether that change landed on what you picked."


def _asked_mm(text: str) -> Optional[float]:
    """The length a request names, in mm: "1/2 in", "1 1/4 in", "12.7 mm". None if it names none."""
    m = _ASKED.search(text)
    if not m:
        return None
    number = sum(float(Fraction(part)) for part in m.group(1).split())
    return number if m.group(2).lower() == "mm" else number * 25.4


def _new_faces(before: dict, after: dict) -> list[dict]:
    def same(a, b):
        return a["type"] == b["type"] and abs(a["area"] - b["area"]) <= 0.01 * max(a["area"], 1.0) \
            and np.linalg.norm(np.subtract(a["centre"], b["centre"])) <= 0.5

    return [f for f in after["faces"] if not any(same(f, b) for b in before["faces"])]


def _fillet(before: dict, after: dict, edge: dict, asked: Optional[float], inches: bool) -> tuple[str, bool]:
    still = any(e["type"] == edge["type"] and abs(e["length"] - edge["length"]) <= 0.01 * edge["length"]
                and np.linalg.norm(np.subtract(e["centre"], edge["centre"])) <= 0.5 for e in after["edges"])
    if still:
        return "The edge you picked is still there, so the fillet didn't land on it.", False
    points = np.array([*edge["points"], edge["centre"]], float)
    rounds = []
    for f in _new_faces(before, after):
        r = f.get("minor") if f["type"] == "torus" else f.get("radius") if f["type"] == "cylinder" else None
        if r and np.linalg.norm(points - np.asarray(f["centre"], float), axis=1).min() <= 2 * r + 1:
            rounds.append(r)
    if not rounds:
        return "The edge you picked has changed, but I can't find a fillet on it.", False
    r = min(rounds, key=lambda x: abs(x - asked)) if asked else rounds[0]
    if asked and abs(r - asked) > max(0.02 * asked, 0.05):
        return f"The fillet is on the edge you picked, but it's {_length(r, inches)}, not {_length(asked, inches)}.", False
    return f"Checked: the fillet is on the edge you picked, {_length(r, inches)}.", True


def _hole(before: dict, after: dict, face: dict, inches: bool) -> tuple[str, Optional[bool]]:
    if face["type"] != "plane" or "axis" not in face:
        return NOT_MEASURED, None
    normal, centre = np.asarray(face["axis"], float), np.asarray(face["centre"], float)
    verts = np.asarray(face["verts"], float).reshape(-1, 3)
    low, high = verts.min(axis=0) - 0.5, verts.max(axis=0) + 0.5
    for f in _new_faces(before, after):
        if f["type"] != "cylinder" or "axis" not in f:
            continue
        axis, at = np.asarray(f["axis"], float), np.asarray(f["centre"], float)
        along = float(np.dot(axis, normal))
        if abs(along) < 0.5:
            continue
        hit = at + axis * float(np.dot(centre - at, normal)) / along
        if np.all(hit >= low) and np.all(hit <= high):
            return f"Checked: there's a {_length(2 * f['radius'], inches)} hole through the face you picked.", True
    return "No new hole goes through the face you picked.", False


def landed(before: Optional[dict], after: Optional[dict], pick: dict, message: str, inches: bool) -> dict:
    """Did a change asked of a picked edge or face land on it? ``{"said": one line, "landed": True, False or None}``, None
    where it can't be measured: only a fillet on an edge and a hole through a flat face can (#107)."""
    said, hit = _landed(before, after, pick, message, inches)
    return {"said": said, "landed": hit}


def _landed(before, after, pick, message, inches) -> tuple[str, Optional[bool]]:
    if not before or not after or before.get("mesh") or after.get("mesh"):
        return NOT_MEASURED, None
    asked_for = (message or "").rsplit(": ", 1)[-1].lower()
    kind, fid = pick.get("kind"), pick.get("id")
    if kind == "edge" and re.search(r"\b(fillet|round)", asked_for):
        edge = next((e for e in before["edges"] if e["id"] == fid), None)
        return _fillet(before, after, edge, _asked_mm(asked_for), inches) if edge else (NOT_MEASURED, None)
    if kind == "face" and re.search(r"\bhole", asked_for):
        face = next((f for f in before["faces"] if f["id"] == fid), None)
        return _hole(before, after, face, inches) if face else (NOT_MEASURED, None)
    return NOT_MEASURED, None
