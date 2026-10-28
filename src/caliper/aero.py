"""CALI-39 — shape a part for drag, and get back numbers to build to, not a mesh.

whittle's carving studies (CALI-38) hand back a remeshed shape: organic, slightly inflated, and no
longer something Caliper can revise. This runs the other way round, agreed with the whittle-agent
session: **Caliper owns the shape as a script with named dimensions; whittle's ``ParametricStudy``
searches those dimensions against its drag model** and returns the same volume-vs-drag slider — but
every station is a set of numbers. Bringing one back rewrites those numbers in the part's script, so
the part stays parametric, revisable by chat, and measured like any other.

The contract is a module-level ``PARAMS`` dict in the part's script, with ``build(params)`` merging
overrides into it::

    PARAMS = {"width": 1879.6, "depth": 990.6, "height": 1041.4,
              "tail_len": 0.0, "tail_drop": 0.0, "tail_pinch": 0.0, "tail_edge_r": 0.0}

    def build(params):
        p = {**PARAMS, **(params or {})}
        ...

It's read and rewritten with ``ast`` by position, so comments and formatting survive.

Speed: a sweep builds the script ~1000 times, so it runs on a warm :class:`~caliper.sandbox.BuildWorker`
(one sandboxed process, CadQuery imported once) — ~0.1–0.3 s a build instead of 1–2 s. Each build is
CadQuery's exact tessellation (whittle welds it and evens its triangles before scoring), so there is
no voxel remesh and none of the inflation the carving studies had.

``obstacles`` are other parts of the design the part rides behind (the car): whittle uses them for
shelter only — never scored, never moved.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import time
import uuid
from typing import Callable, Optional

from .design import DesignStore

PARAMS_NAME = "PARAMS"

#: Energy to push 1 N of drag for 100 miles, in kWh.
KWH_PER_N_PER_100MI = 160_934.4 / 3.6e6


# ---------------------------------------------------------------------------
# PARAMS: read and rewrite the numbers in a script, leaving everything else alone
# ---------------------------------------------------------------------------
def _params_assign(body: list) -> Optional[ast.Dict]:
    for node in body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == PARAMS_NAME
                and isinstance(node.value, ast.Dict)):
            return node.value
    return None


def _params_node(tree: ast.Module) -> Optional[ast.Dict]:
    """The PARAMS dict: at module level as asked, or — as authors sometimes write it — at the top of
    ``build()``. Either way ``build`` merges overrides into it, so either can be searched."""
    found = _params_assign(tree.body)
    if found is not None:
        return found
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "build":
            return _params_assign(node.body)
    return None


_FOLD = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
         ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}


def _number(node: ast.AST) -> Optional[float]:
    """A plain number, or arithmetic on plain numbers (``70.5 * 25.4`` — inches converted in place)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _number(node.operand)
        if inner is not None:
            return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp) and type(node.op) in _FOLD:
        a, b = _number(node.left), _number(node.right)
        if a is not None and b is not None and not (isinstance(node.op, ast.Div) and b == 0):
            return float(_FOLD[type(node.op)](a, b))
    return None


def read_params(script: str) -> Optional[dict[str, float]]:
    """The numeric entries of the script's module-level ``PARAMS`` dict, or ``None`` if it has none."""
    try:
        node = _params_node(ast.parse(script))
    except SyntaxError:
        return None
    if node is None:
        return None
    out = {}
    for k, v in zip(node.keys, node.values):
        value = _number(v)
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and value is not None:
            out[k.value] = value
    return out


def _format(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def write_params(script: str, values: dict[str, float]) -> str:
    """The script with these ``PARAMS`` entries set to new numbers — nothing else touched.

    Replaces each value by its source position (not by re-printing the module), so comments, layout
    and every other line survive exactly. Raises ``KeyError`` naming any value it can't place.
    """
    node = _params_node(ast.parse(script))
    if node is None:
        raise KeyError(f"the script has no module-level {PARAMS_NAME} dict")
    spans = {}
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and _number(v) is not None:
            spans[k.value] = (v.lineno, v.col_offset, v.end_lineno, v.end_col_offset)
    missing = [name for name in values if name not in spans]
    if missing:
        raise KeyError(f"{PARAMS_NAME} has no numeric entry for {', '.join(map(repr, missing))}")
    lines = script.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode()))
    data = script.encode()
    # rewrite from the end so earlier positions stay valid (col offsets are UTF-8 byte offsets)
    for name in sorted(values, key=lambda n: spans[n][:2], reverse=True):
        l0, c0, l1, c1 = spans[name]
        start, end = offsets[l0 - 1] + c0, offsets[l1 - 1] + c1
        data = data[:start] + _format(values[name]).encode() + data[end:]
    return data.decode()


def shape_signature(script: str) -> str:
    """A fingerprint of the script's geometry code, ignoring the numbers in PARAMS.

    Two scripts that differ only in PARAMS values build the same *kind* of shape, so a study's numbers
    apply to either. If the code changed (a part rebuilt with a new parametrisation), the same names can
    mean something else — "pinch" once narrowed the whole side, now only the panels above the walls.
    """
    params = read_params(script) or {}
    try:
        blank = write_params(script, {k: 0 for k in params}) if params else script
    except (KeyError, SyntaxError):
        blank = script
    return hashlib.sha1(blank.encode()).hexdigest()[:12]


_RADIUS = re.compile(r"(^|_)(r|radius|round|fillet)(_|$)")
_ANGLE = re.compile(r"(deg|angle)")
_SHAPE = re.compile(r"(tail|drop|pinch|taper|nose|boat|chamfer)")


def suggest(name: str, value: float) -> dict:
    """A starting guess at whether to search a parameter, and over what range. The UI lets you edit it."""
    if _RADIUS.search(name):
        return {"search": True, "bounds": [max(0.0, min(value, 5.0)), max(150.0, 4 * value)]}
    if _ANGLE.search(name):
        return {"search": bool(_SHAPE.search(name)), "bounds": [0.0, max(20.0, value)]}
    if _SHAPE.search(name):
        hi = 600.0 if "len" in name or name == "tail" else 300.0
        return {"search": True, "bounds": [0.0, max(hi, value)]}
    span = max(abs(value) * 0.2, 1.0)
    return {"search": False, "bounds": [value - span, value + span]}


# ---------------------------------------------------------------------------
# The study
# ---------------------------------------------------------------------------
def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "aero")


def _mesh(vertices, faces):
    import numpy as np
    from whittle import Mesh

    return Mesh(np.asarray(vertices, dtype=np.float64), np.asarray(faces, dtype=np.int64))


def _bounds_of(vertices):
    import numpy as np

    v = np.asarray(vertices)
    return v.min(axis=0), v.max(axis=0)


def study(store: DesignStore, part_id: str, bounds: dict, *, obstacles=(),
          keep_inset_mm: Optional[float] = None, remove_up_to: float = 0.2, stations: int = 4,
          effort: float = 0.5, speed_kmh: float = 105.0, resolution: int = 20,
          flow=(-1.0, 0.0, 0.0), emit: Optional[Callable] = None,
          build_timeout: float = 20.0) -> dict:
    """Search ``bounds`` (``{name: (lo, hi)}``) of a part's PARAMS for low drag. Returns the run record."""
    import numpy as np
    from whittle import ParametricStudy, io

    from .sandbox import BuildError, BuildWorker

    emit = emit or (lambda *a, **k: None)
    if store.design.part(part_id) is None:
        raise KeyError(f"no part {part_id!r}")
    if not store.is_scripted(part_id):
        raise ValueError(f"'{part_id}' is a mesh right now — roll it back to its script first")
    script = store.read_script(part_id)
    start = read_params(script)
    if not start:
        raise ValueError(f"'{part_id}' has no {PARAMS_NAME} dict to search — make it tunable first")
    if not bounds:
        raise ValueError("choose at least one parameter to search")
    clean = {}
    for name, (lo, hi) in bounds.items():
        if name not in start:
            raise ValueError(f"{PARAMS_NAME} has no {name!r}")
        lo, hi = float(min(lo, hi)), float(max(lo, hi))
        if not lo <= start[name] <= hi:
            raise ValueError(f"{name} = {start[name]:g} is outside the range you gave ({lo:g}–{hi:g})")
        clean[name] = (lo, hi)

    notes = ["whittle's drag model ranks shapes well; its absolute numbers are good to perhaps 30%."]
    obstacle_meshes = []
    for oid in obstacles:
        if oid == part_id:
            continue
        g = store.part_geometry(oid).require_mesh()
        obstacle_meshes.append(_mesh(g.vertices, g.faces))
    if obstacle_meshes:
        notes.append("Sheltered by " + ", ".join(f"'{o}'" for o in obstacles if o != part_id)
                     + ": a face behind its silhouette feels no wind. Read the SAVINGS, not the totals: "
                       "the model scores this part alone, so it misses the part partly filling the car's "
                       "wake (which cuts the car's own drag). What the part really costs the vehicle is "
                       "likely lower than its total here, and the savings, if anything, conservative.")
    else:
        notes.append("Free air: nothing upstream is modelled.")

    t0 = time.time()
    emit("building", f"starting a build worker for '{part_id}'")
    with BuildWorker(script, timeout=build_timeout) as worker:
        count = {"n": 0}

        def build(p):
            count["n"] += 1
            try:
                return worker.build(p)
            except BuildError as e:
                raise RuntimeError(str(e)) from e          # whittle skips a raising candidate

        # does PARAMS, unchanged, reproduce the part as it stands? (a script whose defaults drifted
        # from what's on screen would optimise something else)
        v0, _ = worker.build(start)
        lo0, hi0 = _bounds_of(v0)
        cur = store.part_geometry(part_id).require_mesh().bounds
        drift = float(np.max(np.abs(np.concatenate([lo0 - cur[0], hi0 - cur[1]]))))
        if drift > 2.0:
            notes.append(f"Its {PARAMS_NAME} don't quite reproduce the part as it stands (off by up "
                         f"to {drift:.0f} mm) — the search starts from what PARAMS describe.")

        sweep_study = ParametricStudy(build, clean, start=start, flow=tuple(flow),
                                      speed_kmh=float(speed_kmh), obstacles=obstacle_meshes,
                                      resolution=int(resolution))
        if keep_inset_mm:
            inset = float(keep_inset_mm)
            klo, khi = lo0 + inset, hi0 - inset
            if np.any(khi <= klo):
                raise ValueError(f"an inset of {inset:g} mm leaves no interior to protect")
            sweep_study.keep((tuple(klo.tolist()), tuple(khi.tolist())))
            notes.append(f"The interior {inset:g} mm in from every side is kept whole (the cargo).")

        planned = 6 * len(clean) * (max(5, round(30 * effort)) + 1) * (int(stations) - 1)
        emit("planned", f"searching {len(clean)} number(s): up to ~{planned} builds",
             planned=planned)
        last = {"f": -1.0}

        def progress(f):
            if f - last["f"] < 0.02 and f < 1:
                return
            last["f"] = f
            elapsed = time.time() - t0
            eta = elapsed * (1 - f) / f if f > 0 else None
            emit("progress", f"{f:.0%} · {count['n']} builds"
                 + (f" · ~{eta / 60:.0f} min left" if eta and eta > 90 else
                    f" · ~{eta:.0f}s left" if eta else ""),
                 progress=f, builds=count["n"], eta_s=eta)

        def station(n, removed, drag):
            emit("station", f"station {n}: {removed:.1%} of the volume, drag {drag:.0%} of the start")

        sweep = sweep_study.sweep(remove_up_to=float(remove_up_to), stations=int(stations),
                                  effort=float(effort), seed=0, callback=station, progress=progress)

    if sweep.note:
        notes.extend(n for n in sweep.note.splitlines() if n.strip())
    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out = os.path.join(runs_dir(store), rid)
    os.makedirs(out, exist_ok=True)
    rows, base = [], None
    for i, st in enumerate(sweep):
        with open(os.path.join(out, f"station_{i:02d}.stl"), "wb") as f:
            f.write(io.stl_bytes(st.mesh))
        force = st.metrics.get("force_n")
        base = force if base is None else base
        saved = (base - force) if force is not None else None
        rows.append({
            "index": i, "removed": round(float(st.removed), 4),
            "metrics": {k: (None if v is None else float(v)) for k, v in st.metrics.items()},
            "design": {k: float(v) for k, v in st.design.items()},
            "derived": None if saved is None else {
                "saved_n": round(saved, 2), "saved_lbf": round(saved * 0.224809, 2),
                "saved_kwh_per_100mi": round(saved * KWH_PER_N_PER_100MI, 3)},
        })
    if rows:
        notes.extend(limit_notes(clean, start, rows[-1]["design"]))

    record = {
        "id": rid, "part": part_id, "kind": "parametric", "created": time.time(),
        "bounds": {k: list(v) for k, v in clean.items()}, "start": start,
        "obstacles": [o for o in obstacles if o != part_id], "speed_kmh": float(speed_kmh),
        "notes": notes, "stations": rows, "builds": count["n"], "seconds": round(time.time() - t0),
        "searched": list(clean),
        "script_sig": shape_signature(script),
    }
    with open(os.path.join(out, "run.json"), "w") as f:
        json.dump(record, f, indent=2)
    store.append_history(part_id, {"kind": "aero", "action": "studied", "run": rid,
                                   "searched": list(clean), "stations": len(rows)})
    store.append_log({"kind": "aero", "action": "studied", "part": part_id, "run": rid})
    emit("done", f"{len(rows)} designs back from whittle in {record['seconds']}s "
                 f"({count['n']} builds)", run=rid)
    return record


def limit_notes(bounds: dict, start: dict, best: dict) -> list[str]:
    """Name the parameter that stopped the search, not just "the bounds ran out".

    A value pinned at the top of its range is the one to widen. Pinned at the bottom only counts if it
    didn't start there — a radius left at 0 is a choice, not a limit.
    """
    out = []
    for name, (lo, hi) in bounds.items():
        span, v = (hi - lo) or 1.0, best[name]
        if hi - v <= 0.01 * span:
            out.append(f"{name} ended at its upper limit ({_format(hi)}) — widening it may find more; "
                       f"the volume you allow will then be what limits it.")
        elif v - lo <= 0.01 * span and start[name] - lo > 0.01 * span:
            out.append(f"{name} ended at its lower limit ({_format(lo)}) — it wanted to go further.")
    return out


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
    path = os.path.join(runs_dir(store), rid, "run.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def station_path(store: DesignStore, rid: str, index: int) -> str:
    if "/" in rid or ".." in rid:
        raise ValueError("bad run id")
    return os.path.join(runs_dir(store), rid, f"station_{int(index):02d}.stl")


def adopt(store: DesignStore, rid: str, index: int) -> dict:
    """Write a station's numbers into the part's PARAMS — a new **parametric** revision.

    Only the searched parameters change; the script is otherwise byte-for-byte what it was. The
    revision is built and measured like any other, so the design's checks run on the new shape.
    """
    rec = load_run(store, rid)
    if rec is None:
        raise FileNotFoundError(f"no study {rid!r}")
    st = next((s for s in rec["stations"] if s["index"] == int(index)), None)
    if st is None:
        raise FileNotFoundError(f"study {rid} has no station {index}")
    pid = rec["part"]
    if not store.is_scripted(pid):
        raise ValueError(f"'{pid}' is a mesh right now — roll it back to its script first")
    # The study's numbers only mean what they meant if the script is still the same kind of shape.
    current = store.read_script(pid)
    stale = (rec["script_sig"] != shape_signature(current)) if rec.get("script_sig") \
        else set(rec.get("start", {})) != set(read_params(current) or {})
    if stale:
        raise ValueError(f"this study was run on an earlier version of '{pid}' — its script has been "
                         f"rebuilt since, so these numbers may not mean the same thing. Run it again.")
    # 0.1 mm is finer than foam board can hold; more digits would only be noise in the script
    chosen = {k: round(float(st["design"][k]), 1) for k in rec["searched"]}
    before = store.part_geometry(pid).require_mesh().bounds
    script = write_params(store.read_script(pid), chosen)
    from .whittle_bridge import growth

    pretty = ", ".join(f"{k} {_format(v)}" for k, v in chosen.items())
    version = store.write_part(
        pid, script, action="aero",
        feedback=f"shaped for drag: station {index} ({pretty})",
        extra={"aero_run": rid, "station": int(index), "params": chosen,
               "metrics": st.get("metrics", {}), "derived": st.get("derived")})
    grew = growth(before, store.part_geometry(pid).require_mesh().bounds)
    if grew:
        store.append_history(pid, {"kind": "aero", "action": "grew", "grew_mm": grew,
                                   "version": version})
    return {"version": version, "params": chosen, "grew_mm": grew}
