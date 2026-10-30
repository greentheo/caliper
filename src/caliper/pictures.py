"""CALI-78 (#46) — a picture on it: a T-rex cut out of the side, and it still holds Dad.

A kid asks for "a stool to reach the sink, with a T-rex on it". The question that raises is the engineering
one: can you cut a T-rex out of a panel and still hold Dad?

- **The picture** comes from words (Claude draws a silhouette; a T-rex is built in for working offline) or
  from a drawing on the pad.
- **Where it goes:** a panel nobody stands on (the front, or the one named: "on the side"), upright as you
  look at it from outside, as big as fits inside the glued rim and clear of the holes the panel already has.
- **Made cuttable by hand:** nothing narrower than a jigsaw blade can turn round, no gap narrower than one,
  and nothing inside it that would fall out (an eye). Drill a start hole inside it, then cut.
- **Checked:** the strength check is tried with it cut (the panel's cells taken out of the voxels, as the
  lightening study does). If it doesn't hold, the picture shrinks until it does, or it says it can't.
- **Then it's cut:** written into the part's ``HOLES``, so the patterns, the CNC sheet and the strength check
  on the rebuilt part all see it, and the rebuilt part's check is the number to go by.
"""

from __future__ import annotations

import json
import os
import re
from typing import Callable, Optional

import numpy as np

from .design import DesignStore

IN = 25.4
#: Nothing narrower than this, and no gap narrower: a scroll blade in a jigsaw (or a 1/4 in router bit).
MIN_FEATURE_MM = 0.25 * IN
#: How much of the room it may fill, and how much smaller each try gets when it doesn't hold.
FILL, SHRINK, TRIES = 0.9, 0.8, 5
DEFAULT_MODEL = os.environ.get("CALIPER_MODEL", "claude-opus-4-8")

#: A T-rex, side on, facing right, standing on y = 0 in a 100 box: drawn by hand so it works offline.
TREX = [(0, 52), (10, 56), (22, 60), (34, 66), (44, 70), (54, 74), (62, 79), (66, 88), (76, 93), (90, 93),
        (98, 89), (100, 82), (97, 78), (88, 77), (99, 73), (96, 67), (84, 66), (77, 63), (75, 58), (81, 57),
        (85, 52), (80, 48), (73, 52), (70, 47), (66, 41), (68, 33), (66, 24), (70, 9), (77, 5), (77, 0),
        (61, 0), (59, 7), (57, 22), (55, 29), (51, 31), (49, 25), (46, 11), (51, 5), (52, 0), (37, 0),
        (37, 6), (35, 14), (35, 28), (33, 38), (27, 42), (17, 46), (7, 48)]
BUILT_IN = {"t-rex": TREX, "trex": TREX, "t rex": TREX, "tyrannosaurus": TREX, "dinosaur": TREX, "dino": TREX}

#: Claude draws by putting simple shapes together: its outlines traced point by point came out unrecognisable
#: (and crossed themselves), its cats and rockets built from ellipses and strokes came out right.
_DRAW_SYSTEM = """You draw silhouettes for a kid to cut out of plywood with a jigsaw, by putting simple shapes
together. Reply with ONLY a JSON object: {"shapes": [...]}, each shape one of:
  {"ellipse": [cx, cy, rx, ry, angle_deg]}
  {"stroke": [[x, y], [x, y], ...], "width": w}    a thick line through the points, round ends
  {"polygon": [[x, y], ...]}
All in a 100 x 100 box, x to the right, y UP. They're joined into one solid silhouette, so they must overlap
where they meet. Side on and facing right if it has a front; standing on y = 0 if it stands. Recognisable from
its outline alone: the shape a kid would know it by, with its tell-tale parts. Chunky: nothing thinner than 6,
no gap narrower than 6. 6 to 25 shapes."""


def _shapes(shapes):
    """Claude's shapes, joined into one silhouette."""
    from shapely import affinity
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union

    parts = []
    for sh in shapes:
        if "ellipse" in sh:
            cx, cy, rx, ry, a = (list(sh["ellipse"]) + [0])[:5]
            parts.append(affinity.rotate(affinity.scale(Point(cx, cy).buffer(1, 32), rx, ry), a))
        elif "stroke" in sh and len(sh["stroke"]) >= 2:
            parts.append(LineString(sh["stroke"]).buffer(float(sh.get("width", 6)) / 2, 16))
        elif "polygon" in sh and len(sh["polygon"]) >= 3:
            parts.append(Polygon(sh["polygon"]).buffer(0))
    g = unary_union(parts).buffer(3).buffer(-3)                  # shapes that nearly touch, joined
    return max(getattr(g, "geoms", [g]), key=lambda x: x.area)


# ---------------------------------------------------------------------------
# The picture, as a shape in a unit box (x right, y up)
# ---------------------------------------------------------------------------
def _unit(pts):
    """The largest piece of an outline, without holes, scaled into a unit box (its aspect kept)."""
    from shapely.geometry import Polygon
    from shapely.validation import make_valid

    poly = make_valid(Polygon(np.asarray(pts, float)))
    parts = [g for g in getattr(poly, "geoms", [poly]) if g.geom_type == "Polygon" and g.area > 0]
    if not parts:
        raise ValueError("that drawing doesn't enclose anything: draw round the shape and back to the start")
    poly = Polygon(max(parts, key=lambda g: g.area).exterior)
    x0, y0, x1, y1 = poly.bounds
    k = 1.0 / max(x1 - x0, y1 - y0)
    from shapely import affinity

    return affinity.scale(affinity.translate(poly, -x0, -y0), k, k, origin=(0, 0))


def draw(subject: str, *, use_llm: bool = True, client=None, model: Optional[str] = None):
    """A silhouette of ``subject``: one drawn by hand where there is one (a T-rex), else Claude puts one
    together from simple shapes."""
    key = re.sub(r"[^a-z -]", "", (subject or "").lower()).strip()
    for name, pts in BUILT_IN.items():
        if name in key:
            return _unit(pts)
    if use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY")):
        try:
            if client is None:
                from anthropic import Anthropic  # lazy; may be absent

                client = Anthropic()
            msg = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=3000, system=_DRAW_SYSTEM,
                                         messages=[{"role": "user", "content": f"Draw: {subject}"}])
            text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
            m = re.search(r"\{.*\}", text, re.S)
            return _unit(np.asarray(_shapes(json.loads(m.group(0) if m else text)["shapes"]).exterior.coords))
        except Exception:  # noqa: BLE001 — ask for a drawing
            pass
    raise ValueError(f"I can't draw {subject or 'that'} here: draw it on the pad instead")


def from_drawing(points) -> object:
    """A drawing from the pad (x right, y DOWN, as a screen has it), closed and in a unit box."""
    pts = [(float(x), -float(y)) for x, y in points]
    if len(pts) < 8:
        raise ValueError("draw a bit more: go all the way round the shape")
    return _unit(pts)


# ---------------------------------------------------------------------------
# Where it goes
# ---------------------------------------------------------------------------
def panels(store: DesignStore, part_id: str) -> list[dict]:
    """The flat panels a picture can go on: not one a load lands on face-on. Each with its plane, which way is
    inward, which way is up as you look at it from outside, and the room inside its rim."""
    from shapely.geometry import Polygon

    from . import construction as C
    from . import load_study as L
    from .consistency import _frame, _sides, shapes, tolerance
    from .lighten import MIN_WEB_MM, RIM_MM, _loaded_face_on

    declared = C.declared(store, part_id)
    mesh = store.part_geometry(part_id).require_mesh()
    pieces = shapes(declared)
    _sides(mesh, pieces)
    loads = L.parse_loads(declared["loads"]) if declared.get("loads") else []
    tol = tolerance(mesh)
    out = []
    for pc in pieces:
        if pc["kind"] != "sheet" or len(pc["polys"]) != 1 or _loaded_face_on(pc, loads, tol):
            continue
        o, u, v, n, flat = _frame(pc["polys"][0])
        inward = n * pc["sides"][0]
        up3 = np.array([0.0, 0.0, 1.0]) - inward[2] * inward          # world up, in the panel's plane
        if np.linalg.norm(up3) < 0.5:                                  # lying flat: up is along its length
            spread = flat.max(axis=0) - flat.min(axis=0)
            up3 = v if spread[1] >= spread[0] else u
        up3 = up3 / np.linalg.norm(up3)
        right3 = np.cross(up3, -inward)                                 # as seen from outside
        room = Polygon(flat).buffer(-RIM_MM, join_style=2)
        for h in pc.get("holes") or []:
            rel = np.asarray(h, float) - o
            room = room.difference(Polygon(np.stack([rel @ u, rel @ v], 1)).buffer(MIN_WEB_MM))
        if room.is_empty:
            continue
        out.append({"name": pc["name"], "o": o, "u": u, "v": v, "inward": inward, "t": pc["thickness"],
                    "up": np.array([up3 @ u, up3 @ v]), "right": np.array([right3 @ u, right3 @ v]),
                    "room": room, "area": float(Polygon(flat).area), "holes": len(pc.get("holes") or [])})
    return out


def choose(found: list[dict], where: str = "") -> dict:
    """The panel to put it on: the one the words name ("side", "back", "left"), else the front, else the
    biggest; a panel without holes before one with."""
    if not found:
        raise ValueError("there's no flat panel to put a picture on (nobody stands on, with room inside its rim)")
    words = set(re.findall(r"[a-z]+", (where or "").lower()))
    if words & {"side", "sides", "end", "ends"}:                  # a box's sides are its left and right
        words |= {"side", "left", "right"}
    named = [p for p in found if words & set(re.findall(r"[a-z]+", p["name"].lower())) - {"panel"}]
    pool = named or [p for p in found if "front" in p["name"].lower()] or found
    return max(pool, key=lambda p: (p["holes"] == 0, p["room"].area))


def cuttable(poly):
    """What a jigsaw can follow: nothing narrower than a blade turns round, no gap narrower, no islands."""
    from shapely.geometry import Polygon

    r = MIN_FEATURE_MM / 2
    poly = poly.buffer(r).buffer(-r)                  # close: gaps a blade can't get into
    poly = poly.buffer(-r).buffer(r)                  # open: bits a blade can't get round
    parts = [g for g in getattr(poly, "geoms", [poly]) if g.geom_type == "Polygon" and not g.is_empty]
    if not parts:
        return None
    return Polygon(max(parts, key=lambda g: g.area).exterior).simplify(0.3)


def fit(shape, panel: dict, scale: float = 1.0):
    """The picture on the panel: upright as you look at it, centred in the room, ``scale`` of as big as fits."""
    from shapely import affinity
    from shapely.geometry import Polygon
    from shapely.ops import polylabel

    room = panel["room"]
    room = max(getattr(room, "geoms", [room]), key=lambda g: g.area)
    centre = polylabel(room, tolerance=1.0)
    pts = np.asarray(shape.exterior.coords) - np.asarray(shape.centroid.coords[0])
    placed = lambda k: Polygon(np.asarray(centre.coords[0]) + k * (pts[:, :1] * panel["right"]  # noqa: E731
                                                                   + pts[:, 1:] * panel["up"]))
    lo, hi = 0.0, 2 * max(room.bounds[2] - room.bounds[0], room.bounds[3] - room.bounds[1])
    for _ in range(30):                                  # the biggest that fits
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if room.contains(placed(mid)) else (lo, mid)
    got = cuttable(placed(lo * FILL * scale))
    if got is None or not room.contains(got):
        got = cuttable(affinity.scale(placed(lo * FILL * scale), 0.95, 0.95))
    return got


def to_3d(panel: dict, poly) -> list[list[float]]:
    xy = np.asarray(poly.exterior.coords)[:-1]
    pts = panel["o"] + xy[:, :1] * panel["u"] + xy[:, 1:] * panel["v"]
    return [[round(float(c), 2) for c in pt] for pt in pts]


# ---------------------------------------------------------------------------
# Checked, then cut
# ---------------------------------------------------------------------------
def _try(ctx: dict, panel: dict, poly, min_safety: float) -> Optional[float]:
    """The worst safety with ``poly`` cut out of ``panel``, on the voxels; None if the panel isn't in them."""
    from shapely import contains_xy

    from . import lighten
    from . import load_study as L

    s = ctx["spacing"]
    p = next((x for x in lighten.panels(ctx) if x["name"] == panel["name"]), None)
    if p is None:
        return None
    g = np.stack(np.meshgrid((np.arange(p["shape"][0]) + 0.5) * s + p["lo"][0],
                             (np.arange(p["shape"][1]) + 0.5) * s + p["lo"][1], indexing="ij"), -1)
    covered = contains_xy(poly, g[..., 0], g[..., 1]) & p["inside"]
    solid = lighten._cut_solid(ctx["ls"].solid, p, covered)
    worst = None
    for i in range(len(ctx["loads"])):
        case, _ = L.check_load(ctx, i, min_safety, solid=solid)
        if case.get("safety") is not None:
            worst = case["safety"] if worst is None else min(worst, case["safety"])
    return worst


def put(store: DesignStore, part_id: str, shape, *, subject: str = "picture", where: str = "",
        min_safety: Optional[float] = None, emit: Optional[Callable] = None, strength: bool = True) -> dict:
    """Put ``shape`` on the part: fitted, checked (shrunk until it holds), cut into ``HOLES``, and the rebuilt
    part's strength checked. Returns what it did, for the reply."""
    from . import firstrun, holes
    from . import load_study as L

    emit = emit or (lambda *a, **k: None)
    panel = choose(panels(store, part_id), where)
    emit("step", f"Fitting the {subject} on the {panel['name']}", step="fit")
    poly = fit(shape, panel)
    if poly is None or poly.area < MIN_FEATURE_MM ** 2 * 4:
        raise ValueError(f"there isn't room on the {panel['name']} for a {subject} a jigsaw can cut")
    min_safety = min_safety or firstrun._min_safety(store)
    script = store.read_script(part_id)
    checked, predicted, shrunk = "def loads(" in script and strength, None, 0
    if checked:
        emit("step", "Checking it still holds with the picture cut out", step="check")
        ctx = L.prepare(store, part_id)
        for k in range(TRIES):
            predicted = _try(ctx, panel, poly, min_safety)
            if predicted is None or predicted >= min_safety:
                break
            shrunk += 1
            emit("step", f"Too weak at {predicted:g}x: making it smaller", step="check", safety=predicted)
            poly = fit(shape, panel, scale=SHRINK ** (k + 1))
            if poly is None:
                break
        if predicted is not None and predicted < min_safety:
            return {"ok": False, "panel": panel["name"], "subject": subject, "predicted": predicted,
                    "min_safety": min_safety, "reply": (
                        f"A {subject} on the {panel['name']} would make it too weak: {predicted:g} times over at "
                        f"best, and it needs {min_safety:g}. Try another panel (\"on the side\"), or a smaller one.")}
    emit("step", f"Cutting the {subject} out of the {panel['name']}", step="cut")
    entry = {"piece": panel["name"], "normal": [round(float(c), 6) for c in panel["inward"]],
             "depth": round(float(panel["t"]), 3), "polygons": [to_3d(panel, poly)], "picture": subject}
    script = holes.write(script, [*holes.read(script), entry])
    xy = np.asarray(poly.exterior.coords)
    size = [round(float(np.ptp(xy @ panel["right"])) / IN, 1), round(float(np.ptp(xy @ panel["up"])) / IN, 1)]
    version = store.write_part(part_id, script, action="picture",
                               feedback=f"cut a {subject} out of the {panel['name']}, {size[0]:g} x {size[1]:g} in",
                               extra={"picture": subject, "panel": panel["name"]})
    out = {"ok": True, "panel": panel["name"], "subject": subject, "size_in": size, "version": version,
           "predicted": predicted, "shrunk": shrunk, "min_safety": min_safety, "safety": None}
    if checked:
        emit("step", "Checking the part as it's now built", step="recheck")
        run = L.study(store, part_id, min_safety=min_safety)
        out.update({"safety": run["safety"], "holds": run["holds"], "run": run["id"]})
    out["reply"] = reply(out)
    return out


def reply(got: dict) -> str:
    size = f"{got['size_in'][0]:g} × {got['size_in'][1]:g} in"
    said = f"✓ I cut a {got['subject']} {size} out of the {got['panel']}."
    if got.get("shrunk"):
        said += " I made it smaller to keep it strong."
    if got.get("safety") is None:
        return said + " It doesn't say what it must hold, so I couldn't check it's still strong."
    if got["holds"]:
        return said + f" It still holds, {got['safety']:g} times over (it needs {got['min_safety']:g})."
    return (said + f" ✗ Built, it reads {got['safety']:g} times over and needs {got['min_safety']:g}: "
            f"say **roll it back**, or try a smaller one.")
