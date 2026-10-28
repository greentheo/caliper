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
              "unfolder": unfold_dir(), "sheets": [], "sticks": stick_cuts(C.takeoff(items)), "notes": [
                  "Panels are cut to the outside surface; joints are butt joints, as construction() lays "
                  "them out.",
                  "Score lines: on foam, cut a V-groove on the INSIDE face (the unmarked side) and fold it "
                  "closed; mountain/valley as marked, the marked side is the outside of the box."]}
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
    for g in record["sticks"]:
        lines.append(f"{g['label']}: {g['count']} x {g['stock_len_mm'] / 304.8:g} ft")
        for c in g["cuts"]:
            lines.append(f"    {c['length_mm'] / M.IN:6.1f} in  ({c['length_mm']:.0f} mm)  {c['name']}")
        lines.append("")
    for s in record["sheets"]:
        lines.append(f"{s['label']}: {s['sheets']} sheet(s) of {s['stock']}, {s['utilisation'] * 100:.0f}% used — "
                     f"{', '.join(s['panels'])}")
    return "\n".join(lines) + "\n"


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
