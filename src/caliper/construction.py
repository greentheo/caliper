"""CALI-41 — what a part is built from: what it weighs, where that weight sits, and what to buy.

A part's shape says nothing about its weight: a foam box and a plywood box look the same. So a part
declares how it's built, the way a frame declares its tubes (CALI-40), against one shared materials table
(:mod:`caliper.materials`) — nothing here knows about cargo boxes.

The script keeps its build **choices** in a module-level ``BUILD`` dict, apart from ``PARAMS``: they change
the weight and the shopping list, not the shape, so a drag study of the shape still applies. The pieces
come from ``construction(params, build=None)``::

    BUILD = {"floor_t": 9.525, "walls": "xps", ...}

    def construction(params, build=None):
        p = {**PARAMS, **(params or {})}
        b = {**BUILD, **(build or {})}
        return [
            {"name": "floor", "kind": "sheet", "material": "plywood", "thickness": b["floor_t"],
             "outline": [(x, y, z), ...], "covers": ["paint"]},
            {"name": "post", "kind": "stick", "material": "lumber", "size": "2x2", "a": (..), "b": (..)},
            {"name": "glue & screws", "kind": "lump", "mass": 1.4, "at": (x, y, z)},
        ]

- **sheet** — a panel cut from sheet goods. ``outline`` is its face: a flat polygon in world mm. A panel
  bent to a curve gives ``facets`` (several polygons) instead. ``covers`` says what goes on its faces, one
  entry per face (``["pmf"]``: the outside only).
- **stick** — a straight length from ``a`` to ``b``: lumber by nominal ``size``, or steel tube by ``outer``
  and ``wall``.
- **lump** — anything else, by ``mass`` (kg) at a point ``at``.

A part that declares ``members()`` (a tube frame) is weighed from its tubes. :func:`balance` puts every
weighed part together: the design's weight, its centre of gravity, and what the hitch carries.

The sheet and stick counts are a shopping estimate (panels packed on shelves, cuts packed into sticks),
not a cut plan — that needs the joinery, and comes next.
"""

from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
from typing import Optional

from . import materials as M
from .design import DesignStore

#: Saw kerf between pieces cut from one sheet or stick.
KERF = 3.175
BUILD_NAME = "BUILD"
#: Thicknesses a lumber yard sells, offered as choices for a ``*_t`` entry in BUILD.
THICKNESSES = [6.35, 9.525, 12.7, 15.875, 19.05, 25.4, 38.1, 50.8]


# ---------------------------------------------------------------------------
# Reading what a part declares (in its own process — a script may be LLM-authored)
# ---------------------------------------------------------------------------
_PROBE = """

import json as _json, inspect as _inspect
_b = _json.loads({build!r})
_out = {{}}
if callable(globals().get('construction')):
    _f = construction
    _out['construction'] = _f({{}}, _b) if len(_inspect.signature(_f).parameters) > 1 else _f({{}})
    _out['build'] = {{**(globals().get('BUILD') or {{}}), **_b}}
if callable(globals().get('members')):
    _out['members'] = members({{}})
if callable(globals().get('supports')):
    _out['supports'] = supports({{}})
print('@@BUILT@@' + _json.dumps(_out, default=list))
"""


def declares(script: str) -> bool:
    return "def construction(" in script or "def members(" in script


def declared(store: DesignStore, part_id: str, build: Optional[dict] = None,
             timeout: float = 60.0) -> dict:
    """``construction`` / ``members`` / ``supports`` from the part's script, and the BUILD choices used.

    Empty if the part is a mesh or declares none of them. ``build`` overrides BUILD for a what-if.
    """
    if not store.is_scripted(part_id):
        return {}
    script = store.read_script(part_id)
    if not declares(script):
        return {}
    probe = script + _PROBE.format(build=json.dumps(build or {}))
    try:
        out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                             timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ValueError(f"'{part_id}'s construction() took longer than {timeout:g}s")
    line = next((ln for ln in out.stdout.splitlines() if ln.startswith("@@BUILT@@")), None)
    if line is None:
        tail = [ln for ln in out.stderr.strip().splitlines() if ln.strip()]
        raise ValueError(f"couldn't read what '{part_id}' is built from: "
                         f"{tail[-1] if tail else 'no output'}")
    return json.loads(line[len("@@BUILT@@"):])


def from_members(members: list[dict]) -> list[dict]:
    """A tube frame's members as steel sticks, so a frame weighs in like anything else."""
    return [{"name": m.get("name", f"member {i}"), "kind": "stick", "material": "steel",
             "outer": m["outer"], "wall": m["wall"], "a": m["a"], "b": m["b"]}
            for i, m in enumerate(members)]


# ---------------------------------------------------------------------------
# Geometry: flat polygons in 3D
# ---------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a):
    m = math.sqrt(_dot(a, a))
    return (a[0] / m, a[1] / m, a[2] / m) if m > 1e-12 else (0.0, 0.0, 0.0)


def polygon(pts) -> tuple[float, tuple, tuple]:
    """Area (mm²), centroid and unit normal of a flat polygon given by its corners in order."""
    pts = [tuple(float(v) for v in p) for p in pts]
    n = len(pts)
    if n < 3:
        return 0.0, pts[0] if pts else (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    # Newell's method: robust for any simple polygon, convex or not
    nx = ny = nz = 0.0
    for i, p in enumerate(pts):
        q = pts[(i + 1) % n]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if mag < 1e-12:
        return 0.0, tuple(sum(c) / n for c in zip(*pts)), (0.0, 0.0, 1.0)
    normal = (nx / mag, ny / mag, nz / mag)
    total, acc = 0.0, [0.0, 0.0, 0.0]
    p0 = pts[0]
    for i in range(1, n - 1):
        a = 0.5 * _dot(_cross(_sub(pts[i], p0), _sub(pts[i + 1], p0)), normal)   # signed, for concave
        total += a
        for k in range(3):
            acc[k] += a * (p0[k] + pts[i][k] + pts[i + 1][k]) / 3.0
    centroid = tuple(c / total for c in acc) if abs(total) > 1e-12 else tuple(sum(c) / n for c in zip(*pts))
    return mag / 2.0, centroid, normal


def flatten(pts, normal=None) -> list[tuple[float, float]]:
    """A flat polygon's corners in its own plane (mm): the start of a cut outline."""
    pts = [tuple(float(v) for v in p) for p in pts]
    normal = normal or polygon(pts)[2]
    u = next((_unit(_sub(pts[(i + 1) % len(pts)], p)) for i, p in enumerate(pts)
              if math.dist(pts[(i + 1) % len(pts)], p) > 1e-6), (1.0, 0.0, 0.0))
    v = _cross(normal, u)
    o = pts[0]
    return [(_dot(_sub(p, o), u), _dot(_sub(p, o), v)) for p in pts]


def min_rect(pts2d) -> tuple[float, float]:
    """The smallest rectangle (long, short) a flat outline fits in, trying each edge as the base."""
    best = None
    n = len(pts2d)
    for i in range(n):
        (x0, y0), (x1, y1) = pts2d[i], pts2d[(i + 1) % n]
        ang = math.atan2(y1 - y0, x1 - x0)
        c, s = math.cos(-ang), math.sin(-ang)
        xs = [x * c - y * s for x, y in pts2d]
        ys = [x * s + y * c for x, y in pts2d]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if best is None or w * h < best[0] * best[1] - 1e-9:
            best = (w, h)
    w, h = best or (0.0, 0.0)
    return (max(w, h), min(w, h))


def _coplanar(parts) -> bool:
    _, c0, n0 = parts[0]
    return all(abs(abs(_dot(n, n0)) - 1.0) < 1e-4 and abs(_dot(_sub(c, c0), n0)) < 0.5
               for _, c, n in parts[1:])


# ---------------------------------------------------------------------------
# Take-off: every piece's weight and where it sits
# ---------------------------------------------------------------------------
def _g(v: float) -> str:
    return f"{v:g}"


def tube_area(outer: float, wall: float) -> float:
    """Square tube's steel (mm²) for its weight: the nominal wall, corners rounded as welded tube's are
    (outside radius 2x the wall). 2x2x1/8 -> 3.08 lb/ft, against a catalog's 3.05. (A frame study's
    stiffness uses AISC's thinner *design* wall, 0.93x — right for strength, ~7% light for weight.)"""
    if 2 * wall >= outer - 0.01:
        return outer * outer
    return outer * outer - (outer - 2 * wall) ** 2 - (4 - math.pi) * 3 * wall * wall


def tube_label(outer: float, wall: float) -> str:
    o = _g(round(outer / M.IN, 3))
    if 2 * wall >= outer - 0.01:
        return f"{o}x{o} solid steel bar"
    return f"{o}x{o}x{M.nominal(wall).removesuffix(' in')} steel tube"


def piece(item: dict) -> list[dict]:
    """One declared item as take-off rows: the piece itself, then whatever covers it."""
    kind, name = item.get("kind"), item.get("name") or item.get("kind") or "piece"
    if kind == "sheet":
        mat = M.sheet(item["material"])
        t = float(item["thickness"])
        polys = [item["outline"]] if item.get("outline") else list(item.get("facets") or [])
        if not polys:
            raise ValueError(f"sheet {name!r} has no outline")
        parts = [polygon(p) for p in polys]
        area = sum(a for a, _, _ in parts)
        at = tuple(sum(a * c[k] for a, c, _ in parts) / area for k in range(3)) if area else parts[0][1]
        flat = len(parts) == 1 or _coplanar(parts)
        if flat:
            n0 = parts[0][2]
            flat_pts = flatten([p for poly in polys for p in poly], n0)
            size = min_rect(flat_pts) if len(polys) == 1 else _bbox2d(flat_pts)
        else:                        # bent: area is right, the size only roughly (no unrolling yet)
            size = (math.sqrt(area * 2), math.sqrt(area / 2))
        rows = [{"name": name, "kind": "sheet", "material": item["material"], "thickness": t,
                 "label": f"{M.nominal(t)} {mat['name']}", "area_mm2": area,
                 "mass_kg": area * 1e-6 * t * 1e-3 * mat["density"], "at": list(at),
                 "size_mm": [round(size[0], 1), round(size[1], 1)], "flat": flat,
                 "group": item.get("group")}]
        for cover in item.get("covers") or []:
            if not cover or cover == "none":
                continue
            cv = M.covering(cover)
            rows.append({"name": f"{cv['name']} on {name}", "kind": "covering", "material": cover,
                         "label": cv["name"], "area_mm2": area, "mass_kg": area * 1e-6 * cv["areal"],
                         "at": list(at)})
        return rows
    if kind == "stick":
        a, b = [tuple(float(v) for v in item[k]) for k in ("a", "b")]
        length = math.dist(a, b)
        if "size" in item:
            mat, (s1, s2) = M.stick(item.get("material", "lumber"), item["size"])
            section, label = s1 * s2, f"{item['size']} {mat['name']}"
        else:
            mat = M.STICKS[item.get("material", "steel")]
            o, w = float(item["outer"]), float(item["wall"])
            section, label = tube_area(o, w), tube_label(o, w)
        return [{"name": name, "kind": "stick", "material": item.get("material", "lumber"),
                 "label": label, "length_mm": length, "mass_kg": length * section * 1e-9 * mat["density"],
                 "at": [(a[k] + b[k]) / 2 for k in range(3)], "group": item.get("group")}]
    if kind == "lump":
        return [{"name": name, "kind": "lump", "label": item.get("label") or name,
                 "mass_kg": float(item["mass"]), "at": [float(v) for v in item["at"]]}]
    raise ValueError(f"{name!r}: kind must be sheet, stick or lump, not {kind!r}")


def _bbox2d(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    return (max(w, h), min(w, h))


def takeoff(items: list[dict]) -> list[dict]:
    return [row for item in items for row in piece(item)]


def totals(rows: list[dict]) -> tuple[float, list[float]]:
    """Total mass (kg) and centre of gravity (mm)."""
    mass = sum(r["mass_kg"] for r in rows)
    if mass <= 0:
        return 0.0, [0.0, 0.0, 0.0]
    return mass, [sum(r["mass_kg"] * r["at"][k] for r in rows) / mass for k in range(3)]


# ---------------------------------------------------------------------------
# Bill of materials
# ---------------------------------------------------------------------------
def pack_sheets(sizes: list[tuple[float, float]], stock: tuple[float, float],
                kerf: float = KERF) -> tuple[int, list[tuple[float, float]]]:
    """How many stock sheets these panels need, packed on shelves (first fit, tallest first).

    A shopping estimate: real nesting does better on odd shapes. Returns (sheets, panels too big for one).
    """
    W, H = max(stock), min(stock)
    sheets: list[dict] = []
    too_big = []

    def orient(w, h):              # long side along the sheet if it fits that way
        long, short = max(w, h), min(w, h)
        return [(long, short), (short, long)] if long <= W else [(short, long)]

    for w, h in sorted(sizes, key=lambda s: min(s), reverse=True):
        opts = [(pw, ph) for pw, ph in orient(w, h) if pw <= W and ph <= H]
        if not opts:
            too_big.append((w, h))
            continue
        placed = False
        for sh in sheets:
            for shelf in sh["shelves"]:
                fit = next(((pw, ph) for pw, ph in opts if ph <= shelf["h"] and shelf["x"] + pw <= W), None)
                if fit:
                    shelf["x"] += fit[0] + kerf
                    placed = True
                    break
            if not placed:
                fit = next(((pw, ph) for pw, ph in sorted(opts, key=lambda o: o[1]) if sh["y"] + ph <= H), None)
                if fit:
                    sh["shelves"].append({"h": fit[1], "x": fit[0] + kerf})
                    sh["y"] += fit[1] + kerf
                    placed = True
            if placed:
                break
        if not placed:
            pw, ph = min(opts, key=lambda o: o[1])
            sheets.append({"shelves": [{"h": ph, "x": pw + kerf}], "y": ph + kerf})
    return len(sheets), too_big


def pack_sticks(lengths: list[float], stock_len: float, kerf: float = KERF) -> int:
    """How many stock lengths these cuts need (first fit, longest first). Longer cuts need a splice."""
    bins: list[float] = []
    for cut in sorted(lengths, reverse=True):
        if cut > stock_len:
            bins.extend([0.0] * math.ceil(cut / stock_len))       # spliced from whole sticks
            continue
        for i, left in enumerate(bins):
            if cut <= left:
                bins[i] = left - cut - kerf
                break
        else:
            bins.append(stock_len - cut - kerf)
    return len(bins)


FT2 = M.FT2_MM2


def bom(rows: list[dict]) -> dict:
    """What to buy: sheets by material and thickness, sticks with their cut list, coverings by area."""
    sheets: dict = {}
    for r in (r for r in rows if r["kind"] == "sheet"):
        key = (r["material"], round(r["thickness"], 2))
        g = sheets.setdefault(key, {"material": r["material"], "label": r["label"],
                                    "thickness_mm": r["thickness"], "panels": [], "area_mm2": 0.0})
        g["panels"].append({"name": r["name"], "size_mm": r["size_mm"], "flat": r["flat"]})
        g["area_mm2"] += r["area_mm2"]
    for g in sheets.values():
        stock = M.sheet(g["material"])["stock"]
        n, too_big = pack_sheets([tuple(p["size_mm"]) for p in g["panels"]], stock)
        extra = sum(math.ceil(w * h / (stock[0] * stock[1])) for w, h in too_big)
        g.update({"stock_mm": [max(stock), min(stock)], "count": n + extra,
                  "joined": [p["name"] for p in g["panels"] if tuple(p["size_mm"]) in too_big],
                  "bent": [p["name"] for p in g["panels"] if not p["flat"]],
                  "area_ft2": round(g["area_mm2"] / FT2, 1)})

    sticks: dict = {}
    for r in (r for r in rows if r["kind"] == "stick"):
        g = sticks.setdefault(r["label"], {"label": r["label"], "material": r["material"], "cuts": []})
        g["cuts"].append({"name": r["name"], "length_mm": round(r["length_mm"], 1)})
    for g in sticks.values():
        stock_len = M.STICKS[g["material"]]["stock_len"]
        g.update({"stock_len_mm": stock_len,
                  "count": pack_sticks([c["length_mm"] for c in g["cuts"]], stock_len),
                  "total_mm": round(sum(c["length_mm"] for c in g["cuts"]), 1)})

    coverings: dict = {}
    for r in (r for r in rows if r["kind"] == "covering"):
        g = coverings.setdefault(r["material"], {"material": r["material"], "label": r["label"],
                                                 "area_mm2": 0.0})
        g["area_mm2"] += r["area_mm2"]
    for g in coverings.values():
        cv, ft2 = M.covering(g["material"]), g["area_mm2"] / FT2
        g["area_ft2"] = round(ft2, 1)
        if "canvas_roll_mm" in cv:
            roll_ft = cv["canvas_roll_mm"] / (12 * M.IN)
            g["canvas_yd"] = round(ft2 * (1 + cv["overlap"]) / roll_ft / 3.0, 1)
            g["canvas_roll_in"] = round(cv["canvas_roll_mm"] / M.IN)
        if "glue_ft2_per_gal" in cv:
            g["glue_gal"] = round(ft2 / cv["glue_ft2_per_gal"], 2)
        if "paint_ft2_per_gal_coat" in cv:
            g["paint_gal"] = round(ft2 * cv["coats"] / cv["paint_ft2_per_gal_coat"], 2)
            g["coats"] = cv["coats"]

    lumps = [{"name": r["name"], "mass_kg": round(r["mass_kg"], 2)} for r in rows if r["kind"] == "lump"]
    return {"sheets": list(sheets.values()), "sticks": list(sticks.values()),
            "coverings": list(coverings.values()), "lumps": lumps}


def by_material(rows: list[dict]) -> list[dict]:
    out: dict = {}
    for r in rows:
        g = out.setdefault(r["label"], {"label": r["label"], "kind": r["kind"], "mass_kg": 0.0})
        g["mass_kg"] += r["mass_kg"]
    for g in out.values():
        g["mass_lb"] = round(g["mass_kg"] * M.LB_KG, 1)
        g["mass_kg"] = round(g["mass_kg"], 2)
    return sorted(out.values(), key=lambda g: -g["mass_kg"])


# ---------------------------------------------------------------------------
# BUILD: the choices, read and written in place like PARAMS
# ---------------------------------------------------------------------------
def _build_node(tree: ast.Module) -> Optional[ast.Dict]:
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == BUILD_NAME
                and isinstance(node.value, ast.Dict)):
            return node.value
    return None


def _value(node: ast.AST):
    from .aero import _number

    if isinstance(node, ast.Constant) and (isinstance(node.value, (str, bool)) or node.value is None):
        return node.value
    return _number(node)


def read_build(script: str) -> Optional[dict]:
    try:
        node = _build_node(ast.parse(script))
    except SyntaxError:
        return None
    if node is None:
        return None
    return {k.value: _value(v) for k, v in zip(node.keys, node.values)
            if isinstance(k, ast.Constant) and isinstance(k.value, str)}


def _source(value) -> str:
    from .aero import _format

    if isinstance(value, bool) or value is None:
        return repr(value)
    if isinstance(value, (int, float)):
        return _format(value)
    return json.dumps(str(value))


def write_build(script: str, values: dict) -> str:
    """The script with these BUILD entries changed — comments and every other line untouched."""
    node = _build_node(ast.parse(script))
    if node is None:
        raise KeyError(f"the script has no module-level {BUILD_NAME} dict")
    spans = {k.value: (v.lineno, v.col_offset, v.end_lineno, v.end_col_offset)
             for k, v in zip(node.keys, node.values)
             if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    missing = [k for k in values if k not in spans]
    if missing:
        raise KeyError(f"{BUILD_NAME} has no entry for {', '.join(map(repr, missing))}")
    lines = script.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode()))
    data = script.encode()
    for k in sorted(values, key=lambda n: spans[n][:2], reverse=True):
        l0, c0, l1, c1 = spans[k]
        start, end = offsets[l0 - 1] + c0, offsets[l1 - 1] + c1
        data = data[:start] + _source(values[k]).encode() + data[end:]
    return data.decode()


_STICK_WORDS = ("post", "stud", "stick", "rail", "frame")


def choices(build: dict) -> dict:
    """What each BUILD entry could be, for the page's pickers."""
    sizes = list(M.STICKS["lumber"]["sizes"])
    out = {}
    for k, v in build.items():
        if isinstance(v, bool) or v is None:
            continue
        if isinstance(v, str):
            if v in M.SHEETS:
                out[k] = {"kind": "choice", "options": list(M.SHEETS),
                          "labels": {m: M.SHEETS[m]["name"] for m in M.SHEETS}}
            elif v in sizes or (v == "none" and any(w in k for w in _STICK_WORDS)):
                out[k] = {"kind": "choice", "options": ["none", *sizes]}
            elif v in M.COVERINGS or v == "none":
                out[k] = {"kind": "choice", "options": ["none", *M.COVERINGS],
                          "labels": {"none": "nothing", **{m: c["name"] for m, c in M.COVERINGS.items()}}}
        elif k.endswith("_t") or "thick" in k:
            opts = sorted(set(THICKNESSES) | {float(v)})
            out[k] = {"kind": "choice", "options": opts, "labels": {o: M.nominal(o) for o in opts}}
        else:
            out[k] = {"kind": "number"}
    return out


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def _round3(v):
    return [round(float(x), 1) for x in v]


def report(store: DesignStore, part_id: str, build: Optional[dict] = None) -> dict:
    """One part: weight, centre of gravity, what it's made of, and what to buy."""
    d = declared(store, part_id, build)
    if d.get("construction") is not None:
        items, source = d["construction"], "construction"
    elif d.get("members"):
        items, source = from_members(d["members"]), "members"
    else:
        raise ValueError(f"'{part_id}' doesn't say what it's built from — give its script a "
                         f"construction(params, build) (or members() for a tube frame)")
    rows = takeoff(items)
    mass, cog = totals(rows)
    saved = read_build(store.read_script(part_id)) or {}
    used = d.get("build") or {}
    notes = []
    if source == "members":
        notes.append("Weighed from its tubes' centrelines, joint to joint — within a few percent; "
                     "cut lengths come with the cut plan.")
    bom_ = bom(rows)
    for g in bom_["sheets"]:
        if g["joined"]:
            notes.append(f"{', '.join(g['joined'])}: bigger than a {g['label']} sheet — joined from pieces.")
        if g["bent"]:
            notes.append(f"{', '.join(g['bent'])}: bent panels — weighed by their area; sheet count is rough.")
    return {"part": part_id, "source": source, "build": used, "saved": saved,
            "changed": {k: v for k, v in used.items() if k in saved and saved[k] != v},
            "choices": choices(used),
            "mass_kg": round(mass, 2), "mass_lb": round(mass * M.LB_KG, 1), "cog": _round3(cog),
            "materials": by_material(rows), "bom": bom_, "notes": notes,
            "pieces": [{"name": r["name"], "label": r["label"], "mass_lb": round(r["mass_kg"] * M.LB_KG, 2)}
                       for r in rows]}


def balance(store: DesignStore, build: Optional[dict] = None, payload_lb: float = 0.0) -> dict:
    """Every weighed part together: total weight, centre of gravity, and what the hitch carries.

    The hitch point is the first support a part declares (a frame's receiver mouth). ``payload_lb`` is
    gear or people, set on the floor — the middle of the first sheet whose group is ``floor``.
    """
    build = build or {}
    parts, rows_all, hitch, floor_at = [], [], None, None
    for p in store.design.parts:
        d = declared(store, p.id, build.get(p.id))
        items = d.get("construction")
        if items is None and d.get("members"):
            items = from_members(d["members"])
        if items:
            rows = takeoff(items)
            mass, cog = totals(rows)
            parts.append({"part": p.id, "mass_kg": round(mass, 2), "mass_lb": round(mass * M.LB_KG, 1),
                          "cog": _round3(cog)})
            rows_all.extend(rows)
            if floor_at is None:
                floor_at = next((r["at"] for r in rows if r["kind"] == "sheet" and r.get("group") == "floor"),
                                None)
        if hitch is None and d.get("supports"):
            hitch = [float(v) for v in d["supports"][0]["at"]]
    notes = []
    if payload_lb:
        if floor_at is None:
            notes.append("No part has a floor (a sheet in group 'floor') — the payload isn't placed.")
        else:
            rows_all.append({"name": "payload", "kind": "lump", "label": "payload",
                             "mass_kg": payload_lb / M.LB_KG, "at": list(floor_at)})
            parts.append({"part": "payload", "mass_kg": round(payload_lb / M.LB_KG, 2),
                          "mass_lb": round(payload_lb, 1), "cog": _round3(floor_at)})
    mass, cog = totals(rows_all)
    out = {"parts": parts, "mass_kg": round(mass, 2), "mass_lb": round(mass * M.LB_KG, 1),
           "cog": _round3(cog), "hitch": hitch, "payload_lb": payload_lb, "notes": notes}
    if hitch is not None:
        # the receiver sits ahead of the load (+x toward the car): weight behind it bends it down
        for row in parts:
            arm = (hitch[0] - row["cog"][0]) / M.IN
            row["arm_in"], row["moment_lbin"] = round(arm, 1), round(row["mass_lb"] * arm)
        arm = (hitch[0] - cog[0]) / M.IN
        out.update({"arm_in": round(arm, 1), "moment_lbin": round(mass * M.LB_KG * arm),
                    "force_lb": round(mass * M.LB_KG, 1)})
    else:
        notes.append("No part declares supports() — no hitch point to take the moment about.")
    return out


def adopt(store: DesignStore, part_id: str, values: dict) -> dict:
    """Write BUILD choices into the part's script — a new revision; its shape doesn't change."""
    script = store.read_script(part_id)
    saved = read_build(script)
    if saved is None:
        raise KeyError(f"'{part_id}' has no {BUILD_NAME} dict to write choices into")
    changed = {k: v for k, v in values.items() if saved.get(k) != v}
    if not changed:
        return {"version": store.design.part(part_id).version, "build": saved, "changed": {}}
    for k, v in changed.items():
        if k in saved and isinstance(saved[k], (int, float)) and not isinstance(saved[k], bool):
            changed[k] = float(v)
    script = write_build(script, changed)
    pretty = ", ".join(f"{k} {M.nominal(v) if k.endswith('_t') else v}" for k, v in changed.items())
    version = store.write_part(part_id, script, action="build", feedback=f"built from: {pretty}",
                               extra={"build": changed})
    return {"version": version, "build": read_build(script), "changed": changed}
