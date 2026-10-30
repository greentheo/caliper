"""CALI-51 — the build package: one released, versioned bundle per revision, for the shop.

Everything the design ⇄ optimize loop decided, put in the form a shop builds from
(``specs/caliper-make-loop-spec.md`` §7). A release is filed under ``designs/<slug>/releases/<NNN>/``:

- ``index.html`` — **the build book**, printable: what it is and whether it's ready (the scorecard as
  released), what to buy, the cut lists with their end cuts and bevels, every sheet and plate, and the
  assembly order — a step per stage, each with a drawing of what goes on (and what's already there);
- ``build-book.pdf`` — the same book as a PDF, printed by a headless Chrome where there is one;
- ``plasma/`` — gusset plates as DXF (R12, mm) and SVG; ``router/`` — every nested sheet as DXF and SVG,
  with unfold-to-sheets' 1:1 pattern PDF and seam list for each material;
- ``cutlist.txt``, ``shopping.txt`` / ``shopping.csv``, ``scorecard.json``;
- ``source/`` — each part's script at the version released, and the design's own files, so the release
  can be rebuilt;
- a zip of all of it.

It uses the current cut plan of every part that says what it's built from (making one if the part has
changed since), and the current scorecard (re-scoring if anything's changed since the last card). The
assembly order comes from what the parts are built from: the part that holds the others up first, then
each part in its build stages (frame tubes, gussets, jacks, floor, skeleton, panels, shell, patches), its
skin, then the parts brought together, then the finish. Releasing is the user's call (§5); a package made
while a check fails says so on its cover.
"""

from __future__ import annotations

import csv
import html
import io
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import time
import zipfile
import zlib
from typing import Callable, Optional

from . import construction as C
from . import materials as M
from .design import DesignStore

#: The order a part goes together in, by the layers ``construction._layer`` sorts its pieces into.
BUILD_ORDER = ["tubes", "gussets", "jacks", "floor", "skeleton", "panels", "shell", "patches"]
JACK = {"label": "jacks", "color": "#6b7785"}
GLASS = "#8ccfe0"
BOOK = "index.html"


def releases_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "releases")


def list_releases(store: DesignStore) -> list[dict]:
    root = releases_dir(store)
    if not os.path.isdir(root):
        return []
    out = []
    for rid in sorted(os.listdir(root), reverse=True):
        rec = load_release(store, rid)
        if rec:
            out.append(rec)
    return out


def load_release(store: DesignStore, rid: str) -> Optional[dict]:
    if not rid or "/" in rid or ".." in rid:
        return None
    path = os.path.join(releases_dir(store), rid, "release.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def file_path(store: DesignStore, rid: str, rel: str) -> str:
    """A file of a release, refusing anything outside it."""
    base = os.path.realpath(os.path.join(releases_dir(store), rid))
    path = os.path.realpath(os.path.join(base, rel))
    if not path.startswith(base + os.sep) or not os.path.isfile(path):
        raise FileNotFoundError(rel)
    return path


# ---------------------------------------------------------------------------
# Lengths the way a shop reads them
# ---------------------------------------------------------------------------
def inches(mm: float, sixteenths: bool = True) -> str:
    """12.0 → '12 in'; 1039.4 mm → '40 15/16 in' (to the nearest 1/16)."""
    if not sixteenths:
        return f"{mm / M.IN:.1f} in"
    n = round(mm / M.IN * 16)
    whole, rest = divmod(n, 16)
    if rest == 0:
        return f"{whole} in"
    g = math.gcd(rest, 16)
    frac = f"{rest // g}/{16 // g}"
    return f"{whole} {frac} in" if whole else f"{frac} in"


# ---------------------------------------------------------------------------
# What it's built from, as polygons to draw
# ---------------------------------------------------------------------------
def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _add(a, b):
    return [a[i] + b[i] for i in range(3)]


def _mul(a, s):
    return [v * s for v in a]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return [v / n for v in a]


def _box(a, b, w, h) -> list[list]:
    """A stick as the six faces of a box along a→b, its section w × h turned the way three.js turns a box
    (the shortest rotation from x to the stick's axis), so the drawing matches the viewer."""
    u = _unit(_sub(b, a))
    c = u[0]
    if c > 1 - 1e-9:
        y, z = [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]
    elif c < -1 + 1e-9:
        y, z = [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]
    else:
        k = _unit(_cross([1.0, 0.0, 0.0], u))
        th = math.acos(c)

        def rot(v):
            return _add(_add(_mul(v, math.cos(th)), _mul(_cross(k, v), math.sin(th))), _mul(k, _dot(k, v) * (1 - math.cos(th))))

        y, z = rot([0.0, 1.0, 0.0]), rot([0.0, 0.0, 1.0])
    c4 = [_add(_mul(y, sy * w / 2), _mul(z, sz * h / 2)) for sy, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    A, B = [_add(a, o) for o in c4], [_add(b, o) for o in c4]
    faces = [A[::-1], B]
    for i in range(4):
        j = (i + 1) % 4
        faces.append([A[i], A[j], B[j], B[i]])
    return [(f, []) for f in faces]


def _plate(pl: dict) -> list:
    P = pl["placement"]
    o, u, v, n = (list(map(float, P[k])) for k in ("origin", "u", "v", "normal"))
    out = []
    for side in ((1, -1) if int(pl.get("count", 1)) > 1 else (1,)):
        base = _add(o, _mul(n, side * float(pl.get("offset", 0.0))))

        def at(q):
            return _add(base, _add(_mul(u, float(q[0])), _mul(v, float(q[1]))))

        out.append(([at(q) for q in pl["outline"]], [[at(q) for q in h] for h in pl.get("holes") or []]))
    return out


def pieces(store: DesignStore, part_id: str, jacks: Optional[list] = None) -> list[dict]:
    """The part's pieces as polygons in model space, each with its layer and colour."""
    d = C.declared(store, part_id)
    out = []
    for it in C._items(d) or []:
        kind, layer = it.get("kind"), C._layer(it)
        if kind in ("sheet", "covering"):
            polys = [it["outline"]] if it.get("outline") else list(it.get("facets") or [])
            if not polys:
                continue
            out.append({"name": it.get("name"), "layer": layer, "kind": kind, "material": it.get("material"),
                        "covers": list(it.get("covers") or []),
                        "polys": [([list(map(float, p)) for p in poly], []) for poly in polys]})
        elif kind == "stick":
            if "size" in it:
                w, h = M.STICKS[it.get("material", "lumber")]["sizes"][it["size"]]
            else:
                w = h = float(it["outer"])
            out.append({"name": it.get("name"), "layer": layer, "kind": "stick", "material": it.get("material"),
                        "polys": _box(list(map(float, it["a"])), list(map(float, it["b"])), w, h)})
    for name, pl in (d.get("plates") or {}).items():
        out.append({"name": name, "layer": "gussets", "kind": "plate", "material": "steel", "polys": _plate(pl)})
    for j in jacks or []:
        x, y, z = map(float, j["at"])
        out.append({"name": j.get("name", "jack"), "layer": "jacks", "kind": "jack", "material": "steel",
                    "polys": _box([x, y, z], [x, y, z - 380.0], 50.8, 50.8)})
    colors = {**{k: v["color"] for k, v in C.LAYERS.items()}, "jacks": JACK["color"]}
    for p in out:
        p["part"] = part_id
        p["color"] = colors.get(p["layer"], "#9aa4ad")
    return out


# ---------------------------------------------------------------------------
# A drawing: an isometric-ish view, painted far to near
# ---------------------------------------------------------------------------
class View:
    """A camera looking down at the build from ``azimuth`` (degrees round from +x) and ``elevation``."""

    def __init__(self, everything: list[dict], azimuth: float = 35.0, elevation: float = 26.0,
                 width: int = 880, height: int = 560, pad: int = 24, lift: float = 0.0):
        az, el = math.radians(azimuth), math.radians(elevation)
        self.cam = [math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)]
        d = _mul(self.cam, -1)
        self.right = _unit(_cross(d, [0.0, 0.0, 1.0]))
        self.up = _cross(self.right, d)
        self.light = _unit(_add(_add(_mul(self.right, -0.35), _mul(self.up, 0.85)), _mul(self.cam, 0.55)))
        pts = [q for pc in everything for poly, _ in pc["polys"] for q in poly]
        pts += [_add(q, [0, 0, lift]) for q in pts] if lift else []
        xs = [_dot(q, self.right) for q in pts] or [0.0, 1.0]
        ys = [_dot(q, self.up) for q in pts] or [0.0, 1.0]
        self.x0, self.y1 = min(xs), max(ys)
        span_x, span_y = (max(xs) - self.x0) or 1.0, (self.y1 - min(ys)) or 1.0
        self.s = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)
        self.w, self.h = width, height
        self.ox = (width - span_x * self.s) / 2
        self.oy = (height - span_y * self.s) / 2

    def xy(self, q) -> tuple[float, float]:
        return (self.ox + (_dot(q, self.right) - self.x0) * self.s, self.oy + (self.y1 - _dot(q, self.up)) * self.s)

    def depth(self, poly) -> float:
        return sum(_dot(q, self.cam) for q in poly) / len(poly)


def _shade(hex_color: str, k: float, toward: Optional[str] = None, t: float = 0.0) -> str:
    rgb = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    if toward:
        to = [int(toward[i:i + 2], 16) for i in (1, 3, 5)]
        rgb = [a + (b - a) * t for a, b in zip(rgb, to)]
    return "#" + "".join(f"{max(0, min(255, round(c * k))):02x}" for c in rgb)


def _normal(poly) -> list[float]:
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return _unit(n)


def _png(rgb) -> bytes:
    """An RGB image (h × w × 3, uint8) as a PNG, with nothing but zlib."""
    import numpy as np

    h, w, _ = rgb.shape
    raw = np.concatenate([np.zeros((h, 1), np.uint8), rgb.reshape(h, w * 3)], axis=1).tobytes()

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _rgb(hex_color: str):
    return [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]


def draw(view: View, layers: list[tuple[list[dict], str]], arrows: list[tuple] = (), scale: int = 2,
         supersample: int = 2) -> bytes:
    """A PNG of pieces in styles — ``now`` (in colour), ``done`` (pale, already there) — with optional
    arrows (pairs of model-space points). Drawn through a depth buffer, so pieces that touch (a patch on a
    panel, a rail just inside one) cover each other the way they do in the shop; each face's outline is
    drawn where it isn't hidden. ``scale`` is pixels per point of the view; edges are smoothed by
    rendering ``supersample`` times larger and averaging down."""
    import numpy as np

    R = scale * supersample
    W, H = view.w * R, view.h * R
    zb = np.full((H, W), -np.inf, dtype=np.float32)
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    lines = []

    def sxy(q):
        x, y = view.xy(q)
        return x * R, y * R

    def tri(P, D, color):
        (x0, y0), (x1, y1), (x2, y2) = P
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-9:
            return
        xa, xb = max(int(math.floor(min(x0, x1, x2))), 0), min(int(math.ceil(max(x0, x1, x2))), W - 1)
        ya, yb = max(int(math.floor(min(y0, y1, y2))), 0), min(int(math.ceil(max(y0, y1, y2))), H - 1)
        if xa > xb or ya > yb:
            return
        X, Y = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
        l0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
        l1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
        l2 = 1.0 - l0 - l1
        d = l0 * D[0] + l1 * D[1] + l2 * D[2]
        z = zb[ya:yb + 1, xa:xb + 1]
        m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6) & (d > z)
        z[m] = d[m]
        img[ya:yb + 1, xa:xb + 1][m] = color

    def flat(rings, depth_at, color):
        """A flat polygon with holes, filled even-odd; depth from its plane."""
        pts = [p for r in rings for p in r]
        xa, xb = max(int(min(p[0] for p in pts)), 0), min(int(max(p[0] for p in pts)) + 1, W - 1)
        ya, yb = max(int(min(p[1] for p in pts)), 0), min(int(max(p[1] for p in pts)) + 1, H - 1)
        if xa > xb or ya > yb:
            return
        X, Y = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
        inside = np.zeros(X.shape, bool)
        for r in rings:
            for i, (ax, ay) in enumerate(r):
                bx, by = r[(i + 1) % len(r)]
                if ay == by:
                    continue
                inside ^= ((ay > Y) != (by > Y)) & (X < (bx - ax) * (Y - ay) / (by - ay) + ax)
        d = depth_at(X, Y)
        z = zb[ya:yb + 1, xa:xb + 1]
        m = inside & (d > z)
        z[m] = d[m]
        img[ya:yb + 1, xa:xb + 1][m] = color

    for pcs, style in layers:
        for pc in pcs:
            shift = pc.get("shift") or [0.0, 0.0, 0.0]
            base = pc.get("paint") or pc["color"]
            bias = 6.0 if style == "now" else 0.0           # coplanar with something done: the new piece wins
            if pc.get("kind") == "covering":
                bias += 10.0                                 # a patch lies on the face it covers
            for poly, holes in pc["polys"]:
                poly = [_add(q, shift) for q in poly]
                lit = 0.68 + 0.32 * abs(_dot(_normal(poly), view.light))
                if style == "now":
                    fill, edge, w = _shade(base, lit), _shade(base, 0.5), 0.9
                else:
                    fill, edge, w = _shade(base, 0.6 + 0.4 * lit, "#eef0f2", 0.72), "#a9b1ba", 0.55
                P = [sxy(q) for q in poly]
                D = [_dot(q, view.cam) + bias for q in poly]
                if holes:                                   # a plate: flat, with its holes
                    rings = [P] + [[sxy(_add(q, shift)) for q in h] for h in holes]
                    A = np.array([[x, y, 1.0] for x, y in P])
                    coef = np.linalg.lstsq(A, np.array(D), rcond=None)[0]
                    flat(rings, lambda X, Y, c=coef: c[0] * X + c[1] * Y + c[2], _rgb(fill))
                    for r3 in [poly] + [[_add(q, shift) for q in h] for h in holes]:
                        lines += [(sxy(a), sxy(b), _dot(a, view.cam) + bias, _dot(b, view.cam) + bias, edge, w)
                                  for a, b in zip(r3, r3[1:] + r3[:1])]
                    continue
                for k in range(1, len(poly) - 1):
                    tri([P[0], P[k], P[k + 1]], [D[0], D[k], D[k + 1]], _rgb(fill))
                lines += [(P[i], P[(i + 1) % len(P)], D[i], D[(i + 1) % len(P)], edge, w) for i in range(len(P))]

    # each outline where it isn't behind something: sampled along its length against the depth buffer
    for (x0, y0), (x1, y1), d0, d1, color, w in lines:
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) * 2))
        t = np.linspace(0.0, 1.0, n)
        xs, ys, ds = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, d0 + (d1 - d0) * t
        xi, yi = np.clip(xs.astype(int), 0, W - 1), np.clip(ys.astype(int), 0, H - 1)
        seen = ds + 6.0 >= zb[yi, xi]
        r = max(1, int(round(w * R / 2)))
        for dx in range(-r + 1, r):
            for dy in range(-r + 1, r):
                img[np.clip(yi[seen] + dy, 0, H - 1), np.clip(xi[seen] + dx, 0, W - 1)] = _rgb(color)
    for a, b in arrows:
        (x0, y0), (x1, y1) = sxy(a), sxy(b)
        ang = math.atan2(y1 - y0, x1 - x0)
        head = 11 * R
        segs = [((x0, y0), (x1, y1))] + [((x1 - head * math.cos(ang - s), y1 - head * math.sin(ang - s)), (x1, y1))
                                         for s in (0.4, -0.4)]
        for (ax, ay), (bx, by) in segs:
            n = max(2, int(math.hypot(bx - ax, by - ay) * 2))
            t = np.linspace(0.0, 1.0, n)
            xi = np.clip((ax + (bx - ax) * t).astype(int), 0, W - 1)
            yi = np.clip((ay + (by - ay) * t).astype(int), 0, H - 1)
            for dx in range(-R, R + 1):
                for dy in range(-R, R + 1):
                    img[np.clip(yi + dy, 0, H - 1), np.clip(xi + dx, 0, W - 1)] = (192, 57, 43)
    if supersample > 1:
        img = img.reshape(H // supersample, supersample, W // supersample, supersample, 3).mean(axis=(1, 3))
    return _png(np.round(img).astype(np.uint8))


# ---------------------------------------------------------------------------
# The assembly order
# ---------------------------------------------------------------------------
def _names(pcs) -> list[str]:
    return [p["name"] for p in pcs]


def _sheet_groups(plan: dict, names: list[str]) -> list[dict]:
    return [g for g in plan.get("sheets") or [] if set(g["panels"]) & set(names)]


def _router(pid: str, g: dict) -> str:
    return f"router/{pid}-{g['key']}"


def _say_stage(pid: str, layer: str, pcs: list[dict], plan: dict, ctx: dict) -> tuple[str, list[str], list[str]]:
    """A stage's title, what to do, and the files it's cut from."""
    names = _names(pcs)
    do, files = [], []
    if layer == "tubes":
        title = "Cut and weld the frame"
        for g in plan.get("tubes") or []:
            for t in g["cuts"]:
                ends = "; ".join(f"end {e['end']} {_end_short(e)}" for e in t["ends"])
                do.append(f"Cut the {t['name']} from {g['label']}: {inches(t['length_mm'])} ({t['length_mm']:.0f} mm) — {ends}.")
        do.append("Lay it out on a flat table, tack every joint, check it square (the diagonals of the X equal), "
                  "then weld it out.")
        do.append("Check the first tube against the cut list before cutting the rest — lengths are to the faces "
                  "each tube butts against.")
    elif layer == "gussets":
        title = "Gusset plates"
        for pl in plan.get("plates") or []:
            w, h = pl["size_mm"]
            do.append(f"Plasma-cut {pl['count']} × {pl['name']} from {pl['label']} ({inches(w)} × {inches(h)}) — "
                      f"plasma/{pid}-{pl['name']}.dxf — and weld one each side of the "
                      f"{' / '.join(pl['members'])} joint.")
            files.append(f"plasma/{pid}-{pl['name']}.dxf")
            do += [f"   {n}" for n in pl.get("notes") or []]
    elif layer == "jacks":
        title = "Jacks"
        lb = ctx.get("jack_lb")
        rate = ctx.get("jack_rating")
        do.append(f"Mount the {len(pcs)} jack{'s' if len(pcs) != 1 else ''} where the drawing shows "
                  f"({', '.join(n.replace('_', ' ') for n in names)})"
                  + (f": each carries up to {lb:.0f} lb parked with someone inside — buy them rated "
                     f"{rate:.0f} lb or more." if lb else "."))
        do.append("They push only: let the hitch take the front, then wind them down until they bear.")
        do.append("Prime and paint the steel before the box goes on.")
    elif layer == "floor":
        title = "The floor"
        for g in _sheet_groups(plan, names):
            do.append(f"Cut the {', '.join(n for n in names if n in g['panels'])} from {g['label']} — "
                      f"{_router(pid, g)}/sheets/ ({g['sheets']} sheet{'s' if g['sheets'] != 1 else ''}).")
            files.append(f"{_router(pid, g)}/")
        paint = [c for p in pcs for c in p.get("covers") or [] if c == "paint"]
        if paint:
            do.append("Paint its underside and seal the edges before anything goes on it — the road throws water "
                      "at it.")
    elif layer == "skeleton":
        title = "The skeleton"
        sticks = sorted(pcs, key=lambda p: min(q[2] for poly, _ in p["polys"] for q in poly))
        cuts = {c["name"]: (g["label"], c["length_mm"]) for g in plan.get("sticks") or [] for c in g["cuts"]}
        for p in sticks:
            if p["name"] in cuts:
                lab, mm = cuts[p["name"]]
                do.append(f"{p['name'].replace('_', ' ')}: {lab}, {inches(mm)}.")
        do.append("Glue and screw it together bottom up — the bottom rails to the floor, the posts, the top "
                  "rails, then the roof beams across — and check it square before the glue sets.")
    elif layer == "panels":
        title = "End and side panels"
        for g in _sheet_groups(plan, names):
            do.append(f"Cut the {', '.join(n.replace('_', ' ') for n in names if n in g['panels'])} from "
                      f"{g['label']} — {_router(pid, g)}/ (or by hand from the 1:1 pattern.pdf).")
            files.append(f"{_router(pid, g)}/")
        do.append("Glue them to the floor's edge and the skeleton with foam-safe adhesive; they're cut to the "
                  "outside surface, so trim the inside corners to suit as they go on.")
    elif layer == "shell":
        title = "The shell: bands and roof"
        n_bent = sum(1 for p in pcs if len(p["polys"]) > 1)
        for g in _sheet_groups(plan, names):
            do.append(f"Cut the {len([n for n in names if n in g['panels']])} pieces from {g['label']} — "
                      f"{_router(pid, g)}/ ({g.get('scored', 0)} score lines).")
            files.append(f"{_router(pid, g)}/")
            bev = [b for b in g.get("bevels") or [] if set((b["a"], b["b"])) & set(names)]
            if bev:
                lo, hi = min(b["bevel_min"] for b in bev), max(b["bevel_max"] for b in bev)
                do.append(f"Bevel the {len(bev)} edge joints {lo:.0f}–{hi:.0f}° (each edge at half the angle it "
                          "meets at; the cut list has each one) — or leave the V and fill it.")
        if n_bent:
            do.append(f"Score the V-grooves on the INSIDE face, fold them closed, and glue each band to the next. "
                      f"Fold one band as a test before cutting the rest.")
        do.append("Fill any gaps with spray foam; once it's cured, fair the shell with a rasp and sanding board.")
    elif layer == "patches":
        title = "Glass patches"
        do.append(f"Lay the {', '.join(n.replace('_', ' ') for n in names)} first — a layer of glass where the "
                  "walls work hardest — feathered at the edges so the skin goes over smoothly.")
    else:
        title = layer
        do.append(f"Put on the {', '.join(names)}.")
    return title, do, files


def _end_short(e: dict) -> str:
    if e.get("butts"):
        cut = "square" if e["miter_deg"] < 0.5 else f"mitred {e['miter_deg']:.0f}°"
        return f"{cut} to the side of the {e['butts']}"
    if e.get("carries"):
        return f"square, {inches(e['extend_mm'])} past the joint"
    return "square"


def steps(store: DesignStore, plans: dict, bom: dict, ctx: dict) -> tuple[list[dict], list[dict]]:
    """The assembly order: each step's title, what to do, its files, and what it puts on (to draw)."""
    from . import frame_study as F

    every, by_part = [], {}
    for pid in plans:
        script = store.read_script(pid)
        jk = F.frame_def(store, pid).get("jacks") if "def jacks(" in script else None
        by_part[pid] = pieces(store, pid, jk)
        every += by_part[pid]
    order = sorted(by_part, key=lambda pid: min((q[2] for p in by_part[pid] for poly, _ in p["polys"] for q in poly),
                                                default=0.0))
    out = []

    def add(title, do, files, now, part, kind, **extra):
        out.append({"n": len(out) + 1, "title": title, "do": do, "files": files, "part": part, "kind": kind,
                    "now": now, **extra})

    for pid in order:
        pcs = by_part[pid]
        layers = BUILD_ORDER + sorted({p["layer"] for p in pcs} - set(BUILD_ORDER))
        for layer in layers:
            mine = [p for p in pcs if p["layer"] == layer]
            if mine:
                title, do, files = _say_stage(pid, layer, mine, plans[pid], ctx)
                add(title, do, files, mine, pid, layer)
        skin = [p for p in pcs if any(c.startswith("fiberglass") for c in p.get("covers") or [])]
        if skin:
            cv = [g for g in bom.get(pid, {}).get("coverings", []) if g["material"].startswith("fiberglass")]
            yd = sum(g.get("cloth_yd", 0) for g in cv)
            gal = sum(g.get("epoxy_gal", 0) for g in cv)
            add("Glass the outside",
                [f"Glass the whole outside: {', '.join(g['label'] for g in cv)} — {yd:.1f} yd of cloth "
                 f"({cv[0].get('cloth_roll_in', 50)} in roll) and {gal:.2f} gal of epoxy.",
                 "Overlap the cloth ~2 in at its seams and wrap it round the edges onto the floor; wet it out, "
                 "squeegee it lean, and lightly sand once it has cured.",
                 "The glass is what makes the walls strong — the wall checks count on it."],
                [], [{**p, "paint": GLASS} for p in skin], pid, "skin")
    framed = [pid for pid in order if "def members(" in store.read_script(pid)]
    others = [pid for pid in order if pid not in framed]
    if framed and others:
        f_lb = ctx.get("fixing_lbf")
        lift = 260.0
        moving = [{**p, "shift": [0.0, 0.0, lift]} for pid in others for p in by_part[pid]]
        floor = [q for pid in others for p in by_part[pid] if p["layer"] == "floor" for poly, _ in p["polys"] for q in poly]
        arrows = []
        if floor:                      # at the floor's corners, all but the one hidden behind the box
            z = min(q[2] for q in floor)
            xs, ys = [q[0] for q in floor], [q[1] for q in floor]
            corners = [[x, y, z] for x in (min(xs), max(xs)) for y in (min(ys), max(ys))]
            eye = View(every).cam
            for q in sorted(corners, key=lambda c: _dot(c, eye))[1:]:
                arrows.append((_add(q, [0, 0, lift - 30]), _add(q, [0, 0, 40])))
        add(f"Set the {' and '.join(others)} on the {' and '.join(framed)}",
            [f"Lower the {' and '.join(others)} onto the {' and '.join(framed)} and fasten its floor to the riser and "
             "the spine — bolts through the floor, with fender washers. The frame study counts on the box being "
             "fastened there: its walls carry load into the frame."
             + (f" The hardest-working fixing takes {f_lb:.0f} lbf on a bump." if f_lb else ""),
             "Seal each hole through the floor."],
            [], moving, None, "mount", arrows=arrows)
    paint = sum(g.get("paint_gal", 0) for b in bom.values() for g in b.get("coverings", []))
    add("Finish",
        ["Fill and fair the glass, then paint it: epoxy needs paint over it against the sun"
         + (f" ({paint:.2f} gal of exterior paint in all)." if paint else "."),
         "Go over every fixing and weld once more before the first drive."],
        [], [], None, "finish")
    return out, every


# ---------------------------------------------------------------------------
# What to buy
# ---------------------------------------------------------------------------
def _plate_stock(sizes: list, gap: float = 6.35) -> tuple[int, int]:
    """The smallest rectangle (whole inches) the plates go onto in rows, a plasma kerf and a margin apart."""
    sizes = sorted(([max(w, h), min(w, h)] for w, h in sizes), key=lambda s: -s[1])
    best = None
    for rows in range(1, len(sizes) + 1):
        per = math.ceil(len(sizes) / rows)
        shelves = [sizes[i:i + per] for i in range(0, len(sizes), per)]
        w = max(sum(a + gap for a, _ in sh) for sh in shelves) + gap
        h = sum(max(b for _, b in sh) + gap for sh in shelves) + gap
        dims = (math.ceil(max(w, h) / M.IN), math.ceil(min(w, h) / M.IN))
        if best is None or dims[0] * dims[1] < best[0] * best[1]:
            best = dims
    return best


def shopping(store: DesignStore, plans: dict, bom: dict, lumps: dict, ctx: dict) -> dict:
    """The shopping list, by where it's bought, rounded up to what's sold. Prices are
    ``materials.PRICES`` — guesses — so the total is a guess too."""
    from .scorecard import _sheet_price

    P = M.PRICES
    rows = []

    def add(where, item, qty, usd, used_for=""):
        rows.append({"where": where, "item": item, "qty": qty, "usd": round(usd, 2), "for": used_for})

    for pid, plan in plans.items():
        members = C.declared(store, pid).get("members") or []
        for g in plan.get("tubes") or []:
            m = next((m for m in members if "outer" in m and C.tube_label(float(m["outer"]), float(m["wall"])) == g["label"]), None)
            used = sum(t["length_mm"] for t in g["cuts"]) + 3.0 * len(g["cuts"])
            ft = math.ceil(used / 304.8)
            kg = 0.0
            if m:
                o, w = float(m["outer"]), float(m["wall"])
                kg = ft * 304.8 * (o * o - (o - 2 * w) ** 2) * M.STICKS["steel"]["density"] * 1e-9
            add("steel (metal supplier)", g["label"], f"{ft} ft", kg * P["steel_tube_per_kg"],
                ", ".join(t["name"] for t in g["cuts"]))
        by_t: dict = {}
        for pl in plan.get("plates") or []:
            by_t.setdefault(round(pl["thickness_mm"], 3), []).append(pl)
        for t, pls in by_t.items():
            w_in, h_in = _plate_stock([pl["size_mm"] for pl in pls for _ in range(int(pl["count"]))])
            kg = w_in * h_in * M.IN * M.IN * t * M.SHEETS["steel"]["density"] * 1e-9
            add("steel (metal supplier)", f"{M.nominal(t)} steel plate", f"a {w_in} × {h_in} in piece (a drop will do)",
                kg * P["steel_plate_per_kg"], ", ".join(f"{pl['count']} × {pl['name']}" for pl in pls))
        for g in plan.get("sheets") or []:
            stock = M.sheet(g["material"])["stock"]
            add("lumber yard / home center", f"{g['label']}, {min(stock) / 304.8:g} x {max(stock) / 304.8:g} ft",
                f"{g['sheets']} sheet{'s' if g['sheets'] != 1 else ''}",
                g["sheets"] * _sheet_price(g["material"], g["thickness_mm"], stock),
                f"{len(g['panels'])} piece{'s' if len(g['panels']) != 1 else ''}")
        for g in plan.get("sticks") or []:
            size = g["label"].split()[0]
            add("lumber yard / home center", g["label"], f"{g['count']} × {g['stock_len_mm'] / 304.8:g} ft",
                g["count"] * P["lumber"].get(size, 5.0), f"{len(g['cuts'])} cuts")
    cloth = sum(g.get("cloth_yd", 0) for b in bom.values() for g in b.get("coverings", []))
    epoxy = sum(g.get("epoxy_gal", 0) for b in bom.values() for g in b.get("coverings", []))
    canvas = sum(g.get("canvas_yd", 0) for b in bom.values() for g in b.get("coverings", []))
    glue = sum(g.get("glue_gal", 0) for b in bom.values() for g in b.get("coverings", []))
    paint = sum(g.get("paint_gal", 0) for b in bom.values() for g in b.get("coverings", []))
    if cloth:
        yd = math.ceil(cloth)
        add("composites (glass & epoxy)", "6 oz fiberglass cloth, 50 in wide", f"{yd} yd (uses {cloth:.1f})",
            yd * P["glass_cloth_per_yd"], "the skin and the patches")
    if epoxy:
        buy = max(0.5, math.ceil(epoxy * 2) / 2)
        add("composites (glass & epoxy)", "laminating epoxy (resin + hardener)", f"{buy:g} gal (uses {epoxy:.2f})",
            buy * P["epoxy_per_gal"], "wetting out the glass")
    if canvas:
        yd = math.ceil(canvas)
        add("lumber yard / home center", "10 oz canvas duck", f"{yd} yd", yd * P["canvas_per_yd"], "the skin")
    if glue:
        buy = max(0.25, math.ceil(glue * 4) / 4)
        add("lumber yard / home center", "glue for the canvas", f"{buy:g} gal", buy * P["glue_per_gal"], "the skin")
    if paint:
        qt = math.ceil(paint * 4)
        qty = f"{qt} qt" if qt < 4 else f"{math.ceil(paint)} gal"
        add("lumber yard / home center", "exterior paint", f"{qty} (uses {paint:.2f} gal)",
            (qt / 4 if qt < 4 else math.ceil(paint)) * P["paint_per_gal"], "over the glass, under the floor")
    for pid, ls in lumps.items():
        for row in ls:
            if "plate" in (row.get("label") or ""):
                continue
            add("hardware", f"{row['label']}", "allowance", P["hardware_allowance"],
                "foam-safe adhesive, screws, tape, bolts and fender washers")
    if ctx.get("jacks"):
        rate = ctx.get("jack_rating")
        add("hardware", "trailer stabilizer jack" + (f", rated {rate:.0f} lb or more" if rate else ""),
            f"{ctx['jacks']}", ctx["jacks"] * P.get("jack_each", 35.0), "holding the back up, parked")
    groups: dict = {}
    for r in rows:
        groups.setdefault(r["where"], []).append(r)
    return {"groups": [{"where": k, "rows": v, "usd": round(sum(r["usd"] for r in v), 2)} for k, v in groups.items()],
            "usd": round(sum(r["usd"] for r in rows), 2),
            "basis": P["basis"] + "; rounded up to what's sold, so it's more than the scorecard's cost of what's used"}


def shopping_text(shop: dict) -> str:
    lines = ["SHOPPING LIST", ""]
    for g in shop["groups"]:
        lines.append(f"{g['where'].upper()}  (~${g['usd']:.0f})")
        for r in g["rows"]:
            lines.append(f"  [ ] {r['qty']:<34} {r['item']}  (~${r['usd']:.0f}){'  — ' + r['for'] if r['for'] else ''}")
        lines.append("")
    lines.append(f"TOTAL ~${shop['usd']:.0f}  ({shop['basis']})")
    return "\n".join(lines) + "\n"


def shopping_csv(shop: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["where", "qty", "item", "usd", "for"])
    for g in shop["groups"]:
        for r in g["rows"]:
            w.writerow([g["where"], r["qty"], r["item"], f"{r['usd']:.2f}", r["for"]])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# The PDF: the build book printed by a headless Chrome, where there is one
# ---------------------------------------------------------------------------
def chrome() -> Optional[str]:
    env = os.environ.get("CALIPER_CHROME")
    if env:
        return None if env.lower() in ("none", "off", "0") else env
    for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")):
        if c and os.path.exists(c):
            return c
    return None


def print_pdf(html_path: str, pdf_path: str, timeout: float = 120.0) -> Optional[str]:
    """Print a page to PDF with a headless Chrome (its own throwaway profile). Returns why not, or None."""
    exe = chrome()
    if not exe:
        return "no Chrome here to print it with (set CALIPER_CHROME) — print the build book from the browser"
    with tempfile.TemporaryDirectory() as prof:
        try:
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                            f"--user-data-dir={prof}", "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}",
                            "file://" + os.path.abspath(html_path)],
                           capture_output=True, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as e:
            return f"Chrome couldn't print it: {e}"
    return None if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0 else "Chrome printed nothing"


# ---------------------------------------------------------------------------
# The build book
# ---------------------------------------------------------------------------
CSS = """
@page { size: letter; margin: 0.5in; }
* { box-sizing: border-box; }
body { font: 11pt/1.45 -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; color: #1d2329;
       background: #fff; margin: 0 auto; max-width: 8.5in; padding: 24px; }
h1 { font-size: 26pt; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 16pt; margin: 28px 0 8px; padding-top: 6px; border-top: 2px solid #1d2329; break-after: avoid; }
h3 { font-size: 12pt; margin: 18px 0 6px; break-after: avoid; }
.sub { color: #59636e; font-size: 12pt; }
.muted { color: #6b7580; }
.small { font-size: 9pt; }
.status { display: inline-block; padding: 3px 10px; border-radius: 4px; font-weight: 600; font-size: 10pt; }
.ready { background: #e3f4e8; color: #17663a; } .notready { background: #fde8e6; color: #a1281b; }
.nums { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 14px 0; }
.nums div { border: 1px solid #d5dbe1; border-radius: 6px; padding: 8px 10px; }
.nums b { display: block; font-size: 14pt; } .nums span { font-size: 8.5pt; color: #6b7580; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 6px 0; }
th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #e3e7eb; vertical-align: top; }
th { font-size: 8.5pt; text-transform: uppercase; letter-spacing: 0.04em; color: #59636e; }
td.n { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.box { width: 12px; height: 12px; border: 1.5px solid #1d2329; display: inline-block; border-radius: 2px; }
img.draw { width: 100%; border: 1px solid #e3e7eb; border-radius: 6px; }
.step { break-inside: avoid; margin: 18px 0 26px; }
.step h3 { margin-top: 0; } .step .k { color: #6b7580; font-weight: 600; margin-right: 6px; }
.step ol { margin: 6px 0 0 18px; padding: 0; } .step li { margin: 2px 0; }
.sheets { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.sheets figure { margin: 0; break-inside: avoid; } .sheets img { width: 100%; border: 1px solid #e3e7eb; }
figcaption { font-size: 8.5pt; color: #59636e; }
.trust { font-size: 7.5pt; padding: 1px 5px; border-radius: 3px; background: #eef1f4; color: #59636e; white-space: nowrap; }
.pass { color: #17663a; font-weight: 700; } .fail { color: #a1281b; font-weight: 700; }
.page { break-before: page; }
code { font-size: 9pt; }
"""

TRUST = {"measured": "measured", "model": "model, safe side", "rough": "rough", "guess": "guess"}


def _e(s) -> str:
    return html.escape(str(s))


def _num(v, unit="") -> str:
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        t = f"{v:,.0f}" if abs(v) >= 100 else f"{v:.3g}" if abs(v) < 10 else f"{v:.1f}"
        return f"${t}" if unit == "$" else f"{t} {unit}".strip()
    return _e(v)


def title(name: str) -> str:
    """A design's name for a cover: its first sentence (names made from a prompt run on)."""
    first = name.strip().split(". ")[0].strip()
    return first.rstrip(".") or name


def book(rec: dict, card: dict, shop: dict, plans: dict, steps_: list[dict], notes: list[str]) -> str:
    """The build book, as one printable page."""
    m = card.get("metrics") or {}
    ready = card["summary"]["fail"] == 0 and card["summary"]["unknown"] == 0
    status = (f'<span class="status ready">Ready to cut — {card["summary"]["pass"]} of {len(card["checks"])} checks pass</span>'
              if ready else f'<span class="status notready">Not ready — {card["summary"]["fail"]} check(s) fail, '
              f'{card["summary"]["unknown"]} unknown</span>')
    big = [("weight.total_lb", "all up, with the payload"), ("hitch.tongue_lb", "on the tongue"),
           ("frame.yield_x", "frame yields at × its load"), ("drag.lbf", "drag at speed")]
    nums = "".join(f"<div><b>{_num(m[k]['value'], m[k]['unit'])}</b><span>{_e(lab)}</span></div>"
                   for k, lab in big if k in m)
    nums += f"<div><b>${shop['usd']:,.0f}</b><span>to buy (a guess)</span></div>"
    if "make.sheets" in m:
        nums += f"<div><b>{m['make.sheets']['value']}</b><span>sheets to cut</span></div>"
    weights = [(k.split(".", 1)[1], v) for k, v in m.items() if k.startswith("weight.") and k != "weight.total_lb"]
    nums += "".join(f"<div><b>{_num(v['value'], v['unit'])}</b><span>{_e(pid)} as built</span></div>" for pid, v in weights)
    vers = ", ".join(f"{_e(k)} v{v}" for k, v in rec["versions"].items())
    out = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
           f"<title>{_e(title(rec['design']))} — build package {rec['id']}</title><style>{CSS}</style></head><body>",
           f"<div class='muted small'>CALIPER BUILD PACKAGE · RELEASE {rec['id']} · "
           f"{time.strftime('%B %-d, %Y', time.localtime(rec['created']))}</div>",
           f"<h1>{_e(title(rec['design']))}</h1>",
           f"<p>{status} <span class='muted small'>· {vers}</span></p>",
           f"<img class='draw' src='assembly/finished.png' alt='the finished build'>",
           f"<div class='nums'>{nums}</div>"]
    if notes:
        out.append("<h3>Before you cut</h3><ul>" + "".join(f"<li>{_e(n)}</li>" for n in notes) + "</ul>")
    # what to buy
    out.append("<h2 class='page'>Shopping list</h2><table><tr><th></th><th>qty</th><th>item</th><th>for</th>"
               "<th class='n'>~$</th></tr>")
    for g in shop["groups"]:
        out.append(f"<tr><td colspan='5' style='padding-top:10px'><b>{_e(g['where'])}</b> "
                   f"<span class='muted small'>~${g['usd']:,.0f}</span></td></tr>")
        for r in g["rows"]:
            out.append(f"<tr><td><span class='box'></span></td><td>{_e(r['qty'])}</td><td>{_e(r['item'])}</td>"
                       f"<td class='muted small'>{_e(r['for'])}</td><td class='n'>{r['usd']:,.0f}</td></tr>")
    out.append(f"<tr><td></td><td colspan='3'><b>Total</b> <span class='trust'>guess</span></td>"
               f"<td class='n'><b>${shop['usd']:,.0f}</b></td></tr></table>"
               f"<div class='muted small'>{_e(shop['basis'])}</div>")
    # the cut lists
    out.append("<h2 class='page'>Cut lists</h2>")
    for pid, plan in plans.items():
        for g in plan.get("tubes") or []:
            out.append(f"<h3>{_e(g['label'])} <span class='muted small'>· {_e(pid)}</span></h3><table>"
                       "<tr><th>piece</th><th class='n'>length</th><th class='n'>mm</th><th>ends</th></tr>")
            for t in g["cuts"]:
                ends = "<br>".join(f"{_e(e['end'])}: {_e(_end_short(e))}" for e in t["ends"])
                out.append(f"<tr><td>{_e(t['name'])}</td><td class='n'>{inches(t['length_mm'])}</td>"
                           f"<td class='n'>{t['length_mm']:.0f}</td><td class='small'>{ends}</td></tr>")
            out.append("</table>")
        for g in plan.get("sticks") or []:
            out.append(f"<h3>{_e(g['label'])} <span class='muted small'>· {_e(pid)} · {g['count']} × "
                       f"{g['stock_len_mm'] / 304.8:g} ft</span></h3><table>"
                       "<tr><th>piece</th><th class='n'>length</th><th class='n'>mm</th></tr>")
            for c in g["cuts"]:
                out.append(f"<tr><td>{_e(c['name'])}</td><td class='n'>{inches(c['length_mm'])}</td>"
                           f"<td class='n'>{c['length_mm']:.0f}</td></tr>")
            out.append("</table>")
        if plan.get("plates"):
            out.append(f"<h3>Plates, plasma <span class='muted small'>· {_e(pid)}</span></h3><div class='sheets'>")
            for pl in plan["plates"]:
                w, h = pl["size_mm"]
                out.append(f"<figure><img src='plasma/{_e(pid)}-{_e(pl['name'])}.svg' alt='{_e(pl['name'])}' "
                           f"style='max-height:2.4in;object-fit:contain'><figcaption><b>{pl['count']} × {_e(pl['name'])}</b> — "
                           f"{_e(pl['label'])}, {inches(w)} × {inches(h)}, {pl['mass_kg']:.2f} kg each, "
                           f"{pl['safety']}× · plasma/{_e(pid)}-{_e(pl['name'])}.dxf</figcaption></figure>")
            out.append("</div>")
        for g in plan.get("sheets") or []:
            base = _router(pid, g)
            out.append(f"<h3>{_e(g['label'])} <span class='muted small'>· {_e(pid)} · {g['sheets']} sheet(s) of "
                       f"{_e(g['stock'])}, {g['utilisation'] * 100:.0f}% used</span></h3>"
                       f"<div class='small muted'>{base}/sheets/*.dxf to cut · {base}/pattern.pdf is 1:1 with a "
                       f"scale bar · {len(g['panels'])} pieces"
                       f"{', ' + str(g.get('scored', 0)) + ' score lines' if g.get('scored') else ''}</div><div class='sheets'>")
            for f in g.get("files") or []:
                if f["name"].startswith("sheets/") and f["name"].endswith(".svg"):
                    out.append(f"<figure><img src='{base}/{_e(f['name'])}' alt='{_e(f['name'])}'>"
                               f"<figcaption>{_e(f['name'].split('/')[-1].replace('.svg', ''))}</figcaption></figure>")
            out.append("</div>")
            if g.get("bevels"):
                out.append("<table><tr><th>joint</th><th class='n'>edge</th><th class='n'>bevel each edge</th></tr>")
                for b in g["bevels"]:
                    rng = (f"{b['bevel_min']:.0f}–{b['bevel_max']:.0f}°" if b["bevel_max"] - b["bevel_min"] >= 1
                           else f"{b['bevel_max']:.0f}°")
                    out.append(f"<tr><td>{_e(b['a'])} / {_e(b['b'])}</td><td class='n'>{inches(b['length_mm'], False)}</td>"
                               f"<td class='n'>{rng}</td></tr>")
                out.append("</table>")
    # the assembly order
    out.append("<h2 class='page'>Assembly</h2>")
    for s in steps_:
        out.append(f"<div class='step'><h3><span class='k'>{s['n']}</span>{_e(s['title'])}</h3>"
                   f"<img class='draw' src='{_e(s['img'])}' alt='step {s['n']}'><ol>"
                   + "".join(f"<li>{_e(d)}</li>" for d in s["do"]) + "</ol></div>")
    # the scorecard as released
    out.append("<h2 class='page'>Scorecard, as released</h2><table><tr><th></th><th>check</th><th class='n'>value</th>"
               "<th class='n'>margin</th><th>trust</th></tr>")
    for c in card["checks"]:
        mark = "<span class='pass'>✓</span>" if c["status"] == "pass" else "<span class='fail'>✗</span>" \
            if c["status"] == "fail" else "?"
        out.append(f"<tr><td>{mark}</td><td>{_e(c.get('label') or c['id'])}</td>"
                   f"<td class='n'>{_num(c.get('value'), c.get('unit', ''))}</td><td class='n'>{_num(c.get('margin'))}</td>"
                   f"<td>{'<span class=trust>' + _e(TRUST.get(c['trust'], c['trust'])) + '</span>' if c.get('trust') else ''}</td></tr>")
    out.append("</table><h3>Objectives</h3><table>")
    for o in card.get("objectives") or []:
        out.append(f"<tr><td>{_e(o.get('label') or o['metric'])}</td><td class='n'>{_num(o.get('value'), o.get('unit', ''))}</td>"
                   f"<td>{'<span class=trust>' + _e(TRUST.get(o['trust'], o['trust'])) + '</span>' if o.get('trust') else ''}</td></tr>")
    out.append("</table>")
    # what's in the package
    out.append("<h2>What's in the package</h2><table>")
    for folder, what in (("plasma/", "gusset plates — DXF (R12, mm) and SVG, for the plasma table"),
                         ("router/", "every nested sheet — DXF and SVG — with a 1:1 pattern.pdf and seam list per material"),
                         ("assembly/", "the drawings in this book, as PNG"),
                         ("cutlist.txt", "every tube, stick, plate and sheet, inches first"),
                         ("shopping.txt, shopping.csv", "this shopping list"),
                         ("scorecard.json", "the scorecard as released, with every number and how far to trust it"),
                         ("source/", "each part's script at the version released, and the design's own files")):
        out.append(f"<tr><td><code>{_e(folder)}</code></td><td>{_e(what)}</td></tr>")
    out.append("</table><p class='muted small'>Made by Caliper. Every number here was measured from the design or "
               "a model of it, and says how far to trust it; the prices are guesses.</p></body></html>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Making a release
# ---------------------------------------------------------------------------
def _next_id(store: DesignStore) -> str:
    root = releases_dir(store)
    have = [int(n) for n in os.listdir(root) if n.isdigit()] if os.path.isdir(root) else []
    return f"{max(have, default=0) + 1:03d}"


def make(store: DesignStore, *, emit: Optional[Callable] = None, pdf: bool = True,
         timeout: float = 180.0) -> dict:
    """Release the design as it stands: cut plans and scorecard brought up to date, everything for the shop
    filed in one versioned folder, and its record returned."""
    from . import cutplan, scorecard

    emit = emit or (lambda *a, **k: None)
    why = cutplan.available()
    if why:
        raise ValueError(f"can't make a build package: {why}")
    fixed = {p.id for p in store.assembly.parts if p.role == "fixed"}
    built = [p for p in store.design.parts
             if p.id not in fixed and store.is_scripted(p.id) and C.declares(store.read_script(p.id))]
    if not built:
        raise ValueError("no part says what it's built from — there's nothing to cut")

    # the cut plans, current for each part's version
    plans, fresh = {}, False
    for p in built:
        runs = cutplan.list_runs(store, p.id)
        if runs and runs[0].get("version") == p.version:
            plans[p.id] = runs[0]
        else:
            emit("cutting", f"a cut plan for {p.id} v{p.version}")
            plans[p.id] = cutplan.run(store, p.id, emit=emit, timeout=timeout)
            fresh = True

    # the scorecard, current for every part's version and the goals as written
    versions = {p.id: p.version for p in store.design.parts}
    cards = scorecard.list_cards(store, 1)
    goals = scorecard.goals_path(store)
    card = cards[0] if cards else None
    if (fresh or card is None or card.get("versions") != versions
            or (os.path.exists(goals) and os.path.getmtime(goals) > card["created"])):
        emit("scoring", "the design as it stands")
        card = scorecard.compute(store, emit=emit)

    m = card.get("metrics") or {}
    jack_lb = (m.get("parked.jack_lb") or {}).get("value")
    ctx = {"jack_lb": jack_lb, "jack_rating": math.ceil(jack_lb * 1.5 / 100.0) * 100 if jack_lb else None,
           "fixing_lbf": (m.get("frame.fixing_lbf") or {}).get("value")}
    bom, lumps = {}, {}
    for p in built:
        r = C.report(store, p.id)
        bom[p.id] = r["bom"]
        lumps[p.id] = [row for row in C.takeoff(C._items(C.declared(store, p.id))) if row["kind"] == "lump"]

    rid = _next_id(store)
    root = os.path.join(releases_dir(store), rid)
    os.makedirs(root)
    emit("drawing", "the assembly order")
    st, every = steps(store, plans, bom, ctx)
    ctx["jacks"] = sum(1 for p in every if p["layer"] == "jacks")
    os.makedirs(os.path.join(root, "assembly"))
    done: list[dict] = []
    for s in st:                       # each drawing framed on what's there by then
        s["img"] = f"assembly/step-{s['n']:02d}.png"
        emit("drawing", f"step {s['n']}: {s['title']}", progress=s["n"] / len(st))
        if s["kind"] == "mount":
            moving = {(p["part"], p["name"], p["layer"]) for p in s["now"]}
            rest = [p for p in done if (p["part"], p["name"], p["layer"]) not in moving]
            png = draw(View(every, lift=260.0), [(rest, "done"), (s["now"], "now")], s.get("arrows") or ())
        elif s["kind"] == "finish":
            png = draw(View(every), [(every, "now")])
        elif s["kind"] == "skin":
            keep = {(p["part"], p["name"]) for p in s["now"]}
            png = draw(View(done), [([p for p in done if (p["part"], p["name"]) not in keep], "done"), (s["now"], "now")])
        else:
            png = draw(View(done + s["now"]), [(done, "done"), (s["now"], "now")])
            done = done + s["now"]
        with open(os.path.join(root, s["img"]), "wb") as f:
            f.write(png)
    with open(os.path.join(root, "assembly", "finished.png"), "wb") as f:
        f.write(draw(View(every), [(every, "now")]))

    # the files, by machine
    emit("filing", "the cut files")
    cut_texts = []
    for pid, plan in plans.items():
        src = os.path.join(cutplan.runs_dir(store), plan["id"])
        for g in plan.get("sheets") or []:
            shutil.copytree(os.path.join(src, g["key"]), os.path.join(root, _router(pid, g)),
                            ignore=shutil.ignore_patterns("panels.obj"))
        for pl in plan.get("plates") or []:
            os.makedirs(os.path.join(root, "plasma"), exist_ok=True)
            for ext in ("dxf", "svg"):
                shutil.copy(os.path.join(src, "plates", f"{pl['name']}.{ext}"),
                            os.path.join(root, "plasma", f"{pid}-{pl['name']}.{ext}"))
        cl = os.path.join(src, "cutlist.txt")
        if os.path.exists(cl):
            with open(cl) as f:
                cut_texts.append(f.read())
    with open(os.path.join(root, "cutlist.txt"), "w") as f:
        f.write("\n".join(cut_texts))
    os.makedirs(os.path.join(root, "source"))
    for p in store.design.parts:
        if store.is_scripted(p.id):
            shutil.copy(store.script_path(p.id), os.path.join(root, "source", f"{p.id}-v{p.version:03d}.py"))
    for name in ("design.yaml", "assembly.yaml", scorecard.GOALS):
        if os.path.exists(os.path.join(store.root, name)):
            shutil.copy(os.path.join(store.root, name), os.path.join(root, "source", name))
    with open(os.path.join(root, "scorecard.json"), "w") as f:
        json.dump(card, f, indent=2, default=str)

    shop = shopping(store, plans, bom, lumps, ctx)
    with open(os.path.join(root, "shopping.txt"), "w") as f:
        f.write(shopping_text(shop))
    with open(os.path.join(root, "shopping.csv"), "w") as f:
        f.write(shopping_csv(shop))

    notes = list(card.get("notes") or [])
    for plan in plans.values():
        notes += [n for n in plan.get("notes") or [] if n not in notes]
    notes.append("Print the pattern PDFs at 100% (no fit-to-page) and put a ruler on the scale bar before cutting "
                 "from them.")
    rec = {"id": rid, "created": time.time(), "design": store.design.name,
           "slug": os.path.basename(store.root), "versions": versions,
           "card": {"created": card["created"], "summary": card["summary"]},
           "ready": card["summary"]["fail"] == 0 and card["summary"]["unknown"] == 0,
           "cutplans": {pid: plan["id"] for pid, plan in plans.items()},
           "shopping_usd": shop["usd"], "steps": [{"n": s["n"], "title": s["title"], "img": s["img"]} for s in st],
           "sheets": sum(g["sheets"] for plan in plans.values() for g in plan.get("sheets") or []),
           "notes": notes}
    with open(os.path.join(root, BOOK), "w") as f:
        f.write(book(rec, card, shop, plans, st, notes))
    if pdf:
        emit("printing", "the build book to PDF")
        rec["pdf_note"] = print_pdf(os.path.join(root, BOOK), os.path.join(root, "build-book.pdf"))
    rec["pdf"] = os.path.exists(os.path.join(root, "build-book.pdf"))
    rec["zip"] = f"{rec['slug']}-release-{rid}.zip"
    files = sorted(os.path.relpath(os.path.join(d, n), root) for d, _, ns in os.walk(root) for n in ns)
    with open(os.path.join(root, "release.json"), "w") as f:      # in the zip too
        json.dump({**rec, "files": files}, f, indent=2)
    files = sorted(set(files) | {"release.json"})
    with zipfile.ZipFile(os.path.join(root, rec["zip"]), "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(root, rel), os.path.join(f"{rec['slug']}-release-{rid}", rel))
    rec["files"] = files + [rec["zip"]]
    with open(os.path.join(root, "release.json"), "w") as f:
        json.dump(rec, f, indent=2)
    for pid in plans:
        store.append_history(pid, {"kind": "release", "action": "released", "release": rid,
                                   "version": versions[pid]})
    store.append_log({"kind": "release", "action": "released", "release": rid, "versions": versions,
                      "ready": rec["ready"]})
    emit("done", f"release {rid}: {len(st)} steps, {rec['sheets']} sheets, ~${shop['usd']:.0f} to buy"
         + ("" if rec["ready"] else " — NOT ready, a check fails"), release=rid)
    return rec
