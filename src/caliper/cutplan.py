"""CALI-45 — a cut plan: the panels a part is built from, flattened and nested onto the sheets they're cut
from, with score lines where a panel folds; and the cut list for its sticks.

The flattening and nesting is Theo's **unfold-to-sheets** (``game-dev/unfold-to-sheets``): it unfolds a
mesh into flat pieces, marks folds as mountain/valley score lines, nests the pieces onto real stock, and
writes each sheet as SVG and DXF (layers: cut, score-valley, score-mountain, seam, label) with an assembly
drawing, a seam list and a printable PDF. Caliper's side is to say what the pieces are:

- The part's ``construction()`` sheets, grouped by material and thickness, become one OBJ each, **one
  group per panel** — the seams are authored, so the unfolder segments by group rather than guessing
  where to cut. A bent panel (facets) keeps its folds inside one piece: on 1 in XPS they're V-grooves
  scored on the inside.
- The stock and the material come from ``materials.SHEETS[...]["cut"]`` and are handed over as objects
  (unfold-to-sheets takes them as well as its own ids), so foam needs no change on that side.
- Sticks (lumber, steel tube) get a cut list: every length, packed onto stock lengths.

The faces are the panels' outside surfaces, so a panel is cut to its outside size; how the edges meet
(butt joints, the end panels inside the shell) is the construction's, not the unfolder's.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
import uuid
from typing import Callable, Optional

from . import construction as C
from . import materials as M
from .design import DesignStore

DRIVER = os.path.join(os.path.dirname(__file__), "unfold_driver.mjs")


def unfold_dir() -> str:
    return os.environ.get("CALIPER_UNFOLD_DIR",
                          os.path.expanduser("~/githubrepo/game-dev/unfold-to-sheets"))


def available() -> Optional[str]:
    """Why a cut plan can't be made here, or None if it can."""
    if not shutil.which("node"):
        return "node isn't installed (unfold-to-sheets runs on node)"
    if not os.path.exists(os.path.join(unfold_dir(), "js", "pipeline.js")):
        return f"unfold-to-sheets isn't at {unfold_dir()} (set CALIPER_UNFOLD_DIR)"
    return None


def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "cutplans")


def panels_obj(items: list[dict], title: str) -> str:
    """Sheet items as an OBJ: one group per panel, in mm. Faces are written as the polygons they are
    (unfold-to-sheets fans them into triangles; the panels here are convex)."""
    lines = [f"# {title} — written by Caliper for unfold-to-sheets", "# units: mm"]
    n = 0
    for it in items:
        polys = [it["outline"]] if it.get("outline") else list(it.get("facets") or [])
        lines.append(f"g {it['name']}")
        for poly in polys:
            for x, y, z in poly:
                lines.append(f"v {x:.3f} {y:.3f} {z:.3f}")
            lines.append("f " + " ".join(str(n + k + 1) for k in range(len(poly))))
            n += len(poly)
    return "\n".join(lines) + "\n"


def _stock(material: str) -> tuple[dict, dict]:
    """unfold-to-sheets' stock and material objects for one of Caliper's sheet materials (mm)."""
    m = M.sheet(material)
    cut = m.get("cut") or {"kerf": 3.175, "margin": 6.35, "grain": False, "fold_deg": 0.0, "note": ""}
    length, width = max(m["stock"]), min(m["stock"])
    stock = {"id": f"{material}-stock", "name": f"{m['name']} {length / 304.8:g} x {width / 304.8:g} ft",
             "length": length, "width": width, "units": "mm", "grain": bool(cut["grain"]),
             "kerf": cut["kerf"], "margin": cut["margin"], "note": cut["note"]}
    return stock, cut


def _material(material: str, thickness: float, cut: dict) -> dict:
    folds = cut["fold_deg"] > 0
    return {"id": f"{material}-{thickness:g}", "name": f"{M.nominal(thickness)} {M.sheet(material)['name']}",
            "foldable": folds, "maxFoldDeg": cut["fold_deg"] if folds else 2, "joint": "butt",
            "thickness": thickness, "units": "mm", "note": cut["note"]}


def _unfold(obj_text: str, out: str, name: str, stock: dict, material: dict, timeout: float,
            min_score: float = 0.0) -> dict:
    os.makedirs(out, exist_ok=True)
    obj = os.path.join(out, "panels.obj")
    with open(obj, "w") as f:
        f.write(obj_text)
    job = {"obj": obj, "out": out, "name": name, "units": "mm", "stock": stock, "material": material,
           "unfold_dir": unfold_dir(), "rotations": 8, "min_score_deg": min_score}
    try:
        res = subprocess.run(["node", DRIVER], input=json.dumps(job), capture_output=True, text=True,
                             timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ValueError(f"unfolding {name} took longer than {timeout:g}s")
    last = (res.stdout.strip().splitlines() or [""])[-1]
    if res.returncode != 0 or not last.startswith("{"):
        tail = [ln for ln in res.stderr.strip().splitlines() if ln.strip()]
        raise ValueError(f"unfold-to-sheets failed on {name}: {tail[-1] if tail else 'no output'}")
    return json.loads(last)


def stick_cuts(rows: list[dict]) -> list[dict]:
    """The cut list: every stick, longest first, packed onto its stock length."""
    out = []
    for g in C.bom(rows)["sticks"]:
        cuts = sorted(g["cuts"], key=lambda c: -c["length_mm"])
        out.append({"label": g["label"], "material": g["material"], "stock_len_mm": g["stock_len_mm"],
                    "count": g["count"], "cuts": cuts})
    return out


def _seg_dist(p, a, b) -> float:
    ab = [b[i] - a[i] for i in range(3)]
    L2 = sum(v * v for v in ab) or 1.0
    t = max(0.0, min(1.0, sum((p[i] - a[i]) * ab[i] for i in range(3)) / L2))
    return math.dist(p, [a[i] + t * ab[i] for i in range(3)])


def tube_cuts(members: list[dict]) -> list[dict]:
    """A frame's tubes as the shop cuts them: one length per straight run (as ``from_members`` joins them),
    cut to the faces it butts against, and how each end is cut.

    At each end of a run: if a **bigger** tube meets it there, the end butts that tube's side — set back
    to its face (half its width, divided by the sine of the angle between them) and mitred to lie flat on
    it (a vertical stub inside a joint stands for the tube it joins). If only smaller tubes meet it, this
    one carries on past the joint by half their width, so the corner is closed. Otherwise the end is cut
    square on the centreline.
    """
    tubes = [m for m in members if "outer" in m]
    runs = C.from_members(tubes)

    def is_stub(m):
        return math.dist(m["a"], m["b"]) < float(m["outer"])

    def axis(m):
        d = [m["b"][i] - m["a"][i] for i in range(3)]
        n = math.sqrt(sum(v * v for v in d)) or 1.0
        return [v / n for v in d]

    out = []
    for r in runs:
        mine = [m for m in tubes if _seg_dist(m["a"], r["a"], r["b"]) <= 1.0 and _seg_dist(m["b"], r["a"], r["b"]) <= 1.0
                and m.get("group") == r.get("group") and abs(float(m["outer"]) - r["outer"]) < 0.01]
        u = axis(r)
        length = math.dist(r["a"], r["b"])
        ends, cut = [], length
        for end, p in (("a", r["a"]), ("b", r["b"])):
            near = [m for m in tubes if m not in mine
                    and (math.dist(m["a"], p) <= 1.0 or math.dist(m["b"], p) <= 1.0 or _seg_dist(p, m["a"], m["b"]) <= 1.0)]
            hosts = []
            for m in near:
                if is_stub(m):          # through the stub to the tube it stands on
                    q = m["b"] if math.dist(m["a"], p) <= 1.0 else m["a"]
                    hosts += [h for h in tubes if h is not m and h not in mine and not is_stub(h)
                              and (math.dist(h["a"], q) <= 1.0 or math.dist(h["b"], q) <= 1.0 or _seg_dist(q, h["a"], h["b"]) <= 1.0)]
                else:
                    hosts.append(m)
            big = max(hosts, key=lambda h: float(h["outer"]), default=None)
            if big is not None and float(big["outer"]) > r["outer"] + 0.01:
                alpha = math.degrees(math.acos(min(1.0, abs(sum(a * b for a, b in zip(u, axis(big)))))))
                alpha = max(alpha, 10.0)
                back = float(big["outer"]) / 2.0 / math.sin(math.radians(alpha))
                cut -= back
                ends.append({"end": end, "butts": big.get("group") or big.get("name"), "into": C.tube_label(float(big["outer"]), float(big["wall"])),
                             "angle_deg": round(alpha, 1), "miter_deg": round(90.0 - alpha, 1), "setback_mm": round(back, 1)})
            elif hosts:
                over = max(float(h["outer"]) for h in hosts) / 2.0
                cut += over
                ends.append({"end": end, "carries": sorted({h.get("name") for h in hosts}), "extend_mm": round(over, 1),
                             "miter_deg": 0.0})
            else:
                ends.append({"end": end, "free": True, "miter_deg": 0.0})
        out.append({"name": r["name"], "group": r.get("group"), "label": C.tube_label(r["outer"], r["wall"]),
                    "centreline_mm": round(length, 1), "length_mm": round(cut, 1), "ends": ends})
    return out


def _end_text(e: dict) -> str:
    if e.get("butts"):
        cut = "square" if e["miter_deg"] < 0.5 else f"mitred {e['miter_deg']:.0f}°"
        return f"{cut}, butts the side of the {e['into']} ({e['butts']})"
    if e.get("carries"):
        return f"square, runs {e['extend_mm'] / M.IN:.2f} in past the joint to close the corner"
    return "square"


def run(store: DesignStore, part_id: str, *, emit: Optional[Callable] = None,
        timeout: float = 180.0) -> dict:
    """Make the cut plan for one part, file it with the design, and return its record."""
    emit = emit or (lambda *a, **k: None)
    why = available()
    if why:
        raise ValueError(f"can't make a cut plan: {why}")
    d = C.declared(store, part_id)
    items = C._items(d)
    if not items:
        raise ValueError(f"'{part_id}' doesn't say what it's built from — nothing to cut")
    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    root = os.path.join(runs_dir(store), rid)
    groups: dict[tuple, list] = {}
    for it in items:
        if it.get("kind") == "sheet":
            groups.setdefault((it["material"], round(float(it["thickness"]), 3)), []).append(it)
    record = {"id": rid, "part": part_id, "version": store.design.part(part_id).version,
              "created": time.time(), "build": d.get("build") or {},
              "unfolder": unfold_dir(), "sheets": [],
              "sticks": stick_cuts(C.takeoff([it for it in items if not (it.get("kind") == "stick"
                                                                          and it.get("material") == "steel")])),
              "tubes": [], "notes": []}
    if groups:
        record["notes"].append("Panels are cut to the outside surface; joints are butt joints, as "
                               "construction() lays them out.")
    if any((M.sheet(m).get("cut") or {}).get("fold_deg", 0) > 0 for m, _ in groups):
        record["notes"].append("Score lines: on foam, cut a V-groove on the INSIDE face (the unmarked side) "
                               "and fold it closed; mountain/valley as marked, the marked side is the outside.")
    if d.get("members"):
        tubes = tube_cuts(d["members"])
        by: dict[str, list] = {}
        for t in tubes:
            by.setdefault(t["label"], []).append(t)
        stock_len = M.STICKS["steel"]["stock_len"]
        record["tubes"] = [{"label": lab, "stock_len_mm": stock_len,
                            "count": C.pack_sticks([t["length_mm"] for t in ts], stock_len),
                            "cuts": sorted(ts, key=lambda t: -t["length_mm"])} for lab, ts in by.items()]
        record["notes"].append("Tube lengths are cut to the faces they butt against (from the centrelines in "
                               "members()); check them against the first tube before cutting the rest.")
    for (material, thickness), its in sorted(groups.items()):
        stock, cut = _stock(material)
        mat = _material(material, thickness, cut)
        key = f"{material}-{M.nominal(thickness).replace(' ', '').replace('/', '_')}"
        emit("unfolding", f"{len(its)} {mat['name']} panel(s)")
        summary = _unfold(panels_obj(its, f"{part_id}: {mat['name']}"), os.path.join(root, key),
                          f"{part_id} {mat['name']}", stock, mat, timeout, cut.get("score_min_deg", 0.0))
        record["sheets"].append({"key": key, "material": material, "thickness_mm": thickness,
                                 "label": mat["name"], "stock": stock["name"],
                                 "panels": [it["name"] for it in its], **summary})
        record["sheets"][-1]["bevels"] = bevels(record["sheets"][-1])
        if summary.get("missing"):
            record["notes"].append(f"{mat['name']}: {len(summary['missing'])} piece(s) didn't fit a sheet — "
                                   + "; ".join(f"{m['label']}: {m['why']}" for m in summary["missing"]))
    with open(os.path.join(root, "cutplan.json"), "w") as f:
        json.dump(record, f, indent=2)
    with open(os.path.join(root, "cutlist.txt"), "w") as f:
        f.write(cutlist_text(record))
    store.append_history(part_id, {"kind": "cutplan", "action": "made", "run": rid,
                                   "sheets": sum(s["sheets"] for s in record["sheets"])})
    store.append_log({"kind": "cutplan", "action": "made", "part": part_id, "run": rid})
    emit("done", f"{sum(s['sheets'] for s in record['sheets'])} sheet(s), "
                 f"{sum(len(g['cuts']) for g in record['sticks'])} stick cut(s)", run=rid)
    return record


def cutlist_text(record: dict) -> str:
    """The sticks as a shop cut list, inches first."""
    lines = [f"CUT LIST — {record['part']} ({record['id']})", ""]
    for g in record.get("tubes") or []:
        lines.append(f"{g['label']}: {g['count']} x {g['stock_len_mm'] / 304.8:g} ft")
        for t in g["cuts"]:
            lines.append(f"    {t['length_mm'] / M.IN:6.2f} in  ({t['length_mm']:.0f} mm)  {t['name']}")
            for e in t["ends"]:
                lines.append(f"        end {e['end']}: {_end_text(e)}")
        lines.append("")
    for g in record["sticks"]:
        lines.append(f"{g['label']}: {g['count']} x {g['stock_len_mm'] / 304.8:g} ft")
        for c in g["cuts"]:
            lines.append(f"    {c['length_mm'] / M.IN:6.1f} in  ({c['length_mm']:.0f} mm)  {c['name']}")
        lines.append("")
    for s in record["sheets"]:
        lines.append(f"{s['label']}: {s['sheets']} sheet(s) of {s['stock']}, {s['utilisation'] * 100:.0f}% used — "
                     f"{', '.join(s['panels'])}")
        bev = bevels(s)
        if bev:
            lines.append("    bevels — where two pieces meet at an angle, cut each edge at half of it:")
            for b in bev:
                rng = (f"{b['bevel_min']:.0f}–{b['bevel_max']:.0f}°" if b["bevel_max"] - b["bevel_min"] >= 1
                       else f"{b['bevel_max']:.0f}°")
                lines.append(f"      {b['a']} / {b['b']}: {b['length_mm'] / M.IN:.0f} in of edge, bevel {rng}")
    return "\n".join(lines) + "\n"


def bevels(sheet: dict, at_least: float = 2.0) -> list[dict]:
    """The joints in a thick board worth bevelling: the pieces meet at more than ``at_least`` degrees, so
    each edge is cut at half the angle to close the joint (a square edge leaves a V for filler)."""
    if not sheet.get("joints") or sheet.get("thickness_mm", 0) < 10:
        return []
    out = [{"a": j["a"], "b": j["b"], "length_mm": j["length"], "bevel_min": j["angle_min"] / 2.0,
            "bevel_max": j["angle_max"] / 2.0, "bevel_mean": j["angle_mean"] / 2.0}
           for j in sheet["joints"] if j["angle_max"] >= at_least]
    return sorted(out, key=lambda b: (b["a"], b["b"]))


def list_runs(store: DesignStore, part_id: Optional[str] = None) -> list[dict]:
    root = runs_dir(store)
    if not os.path.isdir(root):
        return []
    out = []
    for rid in sorted(os.listdir(root), reverse=True):
        rec = load_run(store, rid)
        if rec and (part_id is None or rec.get("part") == part_id):
            out.append(rec)
    return out


def load_run(store: DesignStore, rid: str) -> Optional[dict]:
    if not rid or "/" in rid or ".." in rid:
        return None
    path = os.path.join(runs_dir(store), rid, "cutplan.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def file_path(store: DesignStore, rid: str, rel: str) -> str:
    """A file of a cut plan, refusing anything outside it."""
    base = os.path.realpath(os.path.join(runs_dir(store), rid))
    path = os.path.realpath(os.path.join(base, rel))
    if not path.startswith(base + os.sep) or not os.path.isfile(path):
        raise FileNotFoundError(rel)
    return path
