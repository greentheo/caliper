"""CALI-38 — the whittle bridge: send a design part to whittle, bring a station back.

**whittle** (Theo's sibling project) evolves a part under physics and returns a *slider* of stations,
not one answer: ``flow`` carves the outside against a drag model, ``load`` lightens under FEA,
``dual`` does both. It runs its own local server with a JSON API — upload a part, start a job with a
setup, poll it, fetch each station as STL — so Caliper drives it over HTTP and needs **no changes to
whittle** and no shared Python environment (Caliper's is OCCT/CadQuery, whittle's is numpy/scipy).

What Caliper adds is what it already knows, and what it can measure that whittle doesn't report:

- **Where it sits** — the part is sent in design (world) coordinates, mm, the units both tools use;
  the flow, symmetry and flat bottom are pre-filled rather than clicked in.
- **Where the air actually is.** A part that rides behind something — a cargo box behind a car — sits
  in that thing's wake, and whittle's drag model can't see a wake it isn't given. Studied in free air,
  the budget goes on rounding a front face the air barely reaches. ``carve="tail"`` lets whittle
  reshape only the downstream end (it can still taper the tail, which is where a trailing body gains).
  *Tried and dropped:* uploading a frozen stand-in for the car alongside the part. whittle's flow study
  deforms one lattice over everything uploaded, so every move that reshapes the part also moves the
  frozen stand-in, the penalty makes it infeasible, and nothing is carved at all (seen live: every
  station 0% removed). Real shelter needs whittle to accept obstacle bodies.
- **Measured, not reported, removal.** whittle's stations are voxel remeshes about half a voxel larger
  than what was sent (seen live: ~1 in on a 74 in box, +8% volume at "0% removed"), so its "% removed"
  is against its own remesh. Caliper measures every station's volume against the part as built, and
  when a station is brought back, how far it reaches past where the part used to be.
- **Units people decide with** — the drag force saved against the starting shape, and what that is in
  **kWh per 100 miles** (1 N over 100 mi = 0.0447 kWh).

whittle's drag model ranks shapes well and gets absolute numbers to perhaps 30%. The ``notes`` on every
run say what it did and didn't model.
"""

from __future__ import annotations

import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Callable, Optional

from .design import DesignStore

WHITTLE_URL = os.environ.get("WHITTLE_URL", "http://127.0.0.1:8765")

#: Energy to push 1 N of drag for 100 miles, in kWh (1 N x 160 934 m / 3.6 MJ).
KWH_PER_N_PER_100MI = 160_934.4 / 3.6e6


class WhittleError(RuntimeError):
    """whittle is unreachable, or refused the request — the message is whittle's own."""


# ---------------------------------------------------------------------------
# HTTP — the whole of whittle's API that Caliper uses
# ---------------------------------------------------------------------------
def _url(path: str, base: Optional[str] = None, query: Optional[dict] = None) -> str:
    url = (base or WHITTLE_URL).rstrip("/") + path
    return url + ("?" + urllib.parse.urlencode(query) if query else "")


def _call(method: str, path: str, *, base: Optional[str] = None, data: Optional[bytes] = None,
          payload: Optional[dict] = None, query: Optional[dict] = None, timeout: float = 30.0,
          raw: bool = False):
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        headers["Content-Type"] = "application/octet-stream"
    req = urllib.request.Request(_url(path, base, query), data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except Exception:  # noqa: BLE001 — not JSON; keep whittle's text as-is
            pass
        raise WhittleError(f"whittle refused {method} {path}: {detail}") from e
    except (urllib.error.URLError, OSError) as e:
        raise WhittleError(f"can't reach whittle at {base or WHITTLE_URL} — is it running? "
                           f"({getattr(e, 'reason', e)})") from e
    return body if raw else json.loads(body or b"{}")


def health(base: Optional[str] = None) -> dict:
    """Is whittle up? Never raises — the page needs a yes/no and a reason."""
    try:
        info = _call("GET", "/api/info", base=base, timeout=3.0)
        return {"ok": True, "url": base or WHITTLE_URL,
                "materials": sorted(info.get("materials", {}))}
    except WhittleError as e:
        return {"ok": False, "url": base or WHITTLE_URL, "error": str(e)}


def upload(stl: bytes, name: str, base: Optional[str] = None) -> dict:
    return _call("POST", "/api/parts", base=base, data=stl, query={"name": name, "units": "mm"},
                 timeout=60.0)


def start(setup: dict, base: Optional[str] = None) -> dict:
    return _call("POST", "/api/jobs", base=base, payload=setup)


def status(job_id: str, base: Optional[str] = None) -> dict:
    return _call("GET", f"/api/jobs/{job_id}", base=base)


def station_stl(job_id: str, index: int, base: Optional[str] = None) -> bytes:
    return _call("GET", f"/api/jobs/{job_id}/stations/{index}/stl", base=base, raw=True,
                 timeout=60.0)


# ---------------------------------------------------------------------------
# Planning a study from what Caliper knows
# ---------------------------------------------------------------------------
def _mesh_of(stl: bytes):
    import trimesh

    return trimesh.load(io.BytesIO(stl), file_type="stl", force="mesh")


def tail_region(bounds, flow, fraction: float = 0.4, pad: float = 5.0) -> list:
    """The downstream ``fraction`` of a part along an axis-aligned flow, as a whittle box.

    Air moving -x (a car driving +x) leaves the part at its *smallest* x, so the tail is the low end.
    """
    axis = max(range(3), key=lambda i: abs(flow[i]))
    if sum(1 for v in flow if abs(v) > 1e-9) != 1:
        raise ValueError("tail-only carving needs an axis-aligned flow (e.g. -x)")
    lo = [float(v) - pad for v in bounds[0]]
    hi = [float(v) + pad for v in bounds[1]]
    span = float(bounds[1][axis]) - float(bounds[0][axis])
    if flow[axis] < 0:
        hi[axis] = float(bounds[0][axis]) + fraction * span
    else:
        lo[axis] = float(bounds[1][axis]) - fraction * span
    return [lo, hi]


def plan(store: DesignStore, part_id: str, *, kind: str = "flow", flow=(-1.0, 0.0, 0.0),
         mirror: Optional[str] = "y", flat=("-z",), carve: str = "anywhere",
         tail_fraction: float = 0.4, keep_inset_mm: Optional[float] = None,
         remove_up_to: float = 0.2, speed_kmh: float = 100.0, stations: int = 6,
         resolution: int = 40, material: str = "xps", cargo_kg: float = 0.0,
         support_bottom_mm: float = 60.0) -> dict:
    """Build the STL and the whittle job body for a part. Pure — nothing is sent yet.

    Returns ``{"stl", "setup", "part_volume", "notes", "part_bounds"}``.
    """
    import numpy as np

    if kind not in ("flow", "dual"):
        raise ValueError("kind must be 'flow' or 'dual'")
    if carve not in ("anywhere", "tail"):
        raise ValueError("carve must be 'anywhere' or 'tail'")
    stl = store.part_stl(part_id)
    part_mesh = _mesh_of(stl)
    if not part_mesh.is_watertight:
        raise ValueError(f"'{part_id}' isn't watertight — whittle can't voxelize or carve it")
    plo, phi = part_mesh.bounds
    voxel = float((phi - plo).max()) / max(int(resolution), 1)
    notes = ["whittle's drag model ranks shapes well; its absolute numbers are good to perhaps 30%.",
             f"whittle rebuilds the part on a ~{voxel:.0f} mm voxel grid, so its stations can come "
             f"back up to ~{voxel / 2:.0f} mm larger than the part. Removal here is measured "
             f"against your part as built, and bringing a station back reports any growth."]

    surfaces = []
    if carve == "tail":
        surfaces.append({"box": tail_region((plo, phi), flow, tail_fraction)})
        notes.append(f"Only the tail (the downstream {tail_fraction:.0%}) may change. The drag is "
                     f"still scored in free air, so the totals include a front face that, behind "
                     f"a car, sits in its wake — read the savings column, not the totals.")
    else:
        notes.append("Free air: nothing upstream is modelled. For a part riding behind something, "
                     "carve the tail only.")

    keep_boxes = []
    if keep_inset_mm:
        inset = float(keep_inset_mm)
        lo, hi = plo + inset, phi - inset
        if np.any(hi <= lo):
            raise ValueError(f"an inset of {inset:g} mm leaves no interior to protect")
        keep_boxes.append([lo.tolist(), hi.tolist()])

    setup = {
        "kind": kind, "flow": [float(v) for v in flow], "mirror": mirror or None,
        "flat": list(flat), "speedKmh": float(speed_kmh),
        "removeUpTo": round(min(max(float(remove_up_to), 0.02), 0.8), 4),
        "resolution": int(resolution), "surfaces": surfaces,
    }
    if kind == "flow":
        setup.update({"stations": int(stations), "keepBoxes": keep_boxes})
    else:
        # held from underneath (it sits on its frame), cargo kept clear inside
        setup.update({
            "material": material, "aeroStations": max(2, min(int(stations), 8)),
            "supports": [{"box": [[float(plo[0]) - 1, float(plo[1]) - 1, float(plo[2]) - 1],
                                  [float(phi[0]) + 1, float(phi[1]) + 1,
                                   float(plo[2]) + support_bottom_mm]]}],
            "cargo": ([{"box": keep_boxes[-1], "kg": float(cargo_kg)}] if keep_boxes else []),
        })
    return {"stl": stl, "setup": setup, "part_volume": float(abs(part_mesh.volume)),
            "notes": notes, "part_bounds": [plo.tolist(), phi.tolist()]}


# ---------------------------------------------------------------------------
# Running it, and keeping the results with the design
# ---------------------------------------------------------------------------
def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "whittle")


def growth(before_bounds, after_bounds, tol_mm: float = 1.0) -> dict:
    """How far a new shape reaches past the old one, per side — ``{"-z": 23.9, ...}`` (mm).

    A part that sits on a frame or clears a car by an inch can't silently gain an inch, and whittle's
    remeshed stations can. Caliper measures it rather than trusting "inward-only".
    """
    out = {}
    for axis, name in enumerate("xyz"):
        below = float(before_bounds[0][axis]) - float(after_bounds[0][axis])
        above = float(after_bounds[1][axis]) - float(before_bounds[1][axis])
        if below > tol_mm:
            out[f"-{name}"] = round(below, 1)
        if above > tol_mm:
            out[f"+{name}"] = round(above, 1)
    return out


def _derive(stations: list[dict], part_volume: float) -> None:
    """The columns people decide with: removal measured against the real part, and force saved."""
    base = None
    for st in stations:
        vol = st.pop("_volume", None)
        if vol is not None and part_volume > 0:
            st["volume_ratio"] = round(vol / part_volume, 4)
            st["removed_part"] = round(1.0 - vol / part_volume, 4)
        force = (st.get("metrics") or {}).get("force_n")
        if force is None:
            continue
        base = force if base is None else base
        saved = base - force
        st["derived"] = {"saved_n": round(saved, 2), "saved_lbf": round(saved * 0.224809, 2),
                         "saved_kwh_per_100mi": round(saved * KWH_PER_N_PER_100MI, 3)}


def run(store: DesignStore, part_id: str, *, emit: Optional[Callable] = None,
        base: Optional[str] = None, poll: float = 1.0, timeout: float = 1800.0, **plan_kw) -> dict:
    """Plan, send, follow, and file a whittle study for one part. Returns the run record."""
    emit = emit or (lambda *a, **k: None)
    planned = plan(store, part_id, **plan_kw)
    emit("planned", f"sending '{part_id}' to whittle ({planned['setup']['kind']} study)")

    uploaded = upload(planned["stl"], f"{part_id}.stl", base=base)
    if not uploaded.get("closed", True):
        planned["notes"].append("whittle says the mesh isn't closed; results may be unreliable.")
    job = start({**planned["setup"], "part": uploaded["id"]}, base=base)
    emit("whittle", "whittle is working…", whittle_job=job["id"])

    deadline, last = time.time() + timeout, -1.0
    while True:
        st = status(job["id"], base=base)
        if st["state"] in ("done", "error", "cancelled"):
            break
        pct = float(st.get("progress") or 0.0)
        if pct - last >= 0.05:
            last = pct
            emit("progress", f"whittle {pct:.0%}", progress=pct)
        if time.time() > deadline:
            raise WhittleError("whittle took too long; it may still be running on its side")
        time.sleep(poll)
    if st["state"] != "done":
        raise WhittleError(f"whittle's study {st['state']}: {st.get('error') or 'no reason given'}")

    result = st["result"]
    wid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out = os.path.join(runs_dir(store), wid)
    os.makedirs(out, exist_ok=True)

    stations = [dict(s, index=i) for i, s in enumerate(result.get("stations", []))]
    emit("fetching", f"bringing back {len(stations)} station(s)")
    for s in stations:
        raw = station_stl(job["id"], s["index"], base=base)
        with open(os.path.join(out, f"station_{s['index']:02d}.stl"), "wb") as f:
            f.write(raw)
        s["_volume"] = float(abs(_mesh_of(raw).volume))
    _derive(stations, planned["part_volume"])

    record = {
        "id": wid, "part": part_id, "kind": planned["setup"]["kind"], "created": time.time(),
        "setup": planned["setup"], "notes": planned["notes"],
        "carve": plan_kw.get("carve", "anywhere"),
        "columns": result.get("columns", []), "stations": stations,
        "rows": result.get("rows"), "whittle": {"url": base or WHITTLE_URL, "job": job["id"]},
        "speed_kmh": planned["setup"]["speedKmh"],
    }
    with open(os.path.join(out, "run.json"), "w") as f:
        json.dump(record, f, indent=2, default=str)
    store.append_history(part_id, {"kind": "whittle", "action": "studied", "run": wid,
                                   "study": record["kind"], "stations": len(stations),
                                   "carve": record["carve"]})
    store.append_log({"kind": "whittle", "action": "studied", "part": part_id, "run": wid})
    emit("done", f"{len(stations)} station(s) back from whittle", run=wid)
    return record


def list_runs(store: DesignStore, part_id: Optional[str] = None) -> list[dict]:
    root = runs_dir(store)
    out = []
    if not os.path.isdir(root):
        return out
    for wid in sorted(os.listdir(root), reverse=True):
        rec = load_run(store, wid)
        if rec and (part_id is None or rec.get("part") == part_id):
            out.append(rec)
    return out


def load_run(store: DesignStore, wid: str) -> Optional[dict]:
    if not wid or "/" in wid or ".." in wid:
        return None
    path = os.path.join(runs_dir(store), wid, "run.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def station_path(store: DesignStore, wid: str, index: int) -> str:
    if "/" in wid or ".." in wid:
        raise ValueError("bad run id")
    return os.path.join(runs_dir(store), wid, f"station_{int(index):02d}.stl")


def adopt(store: DesignStore, wid: str, index: int) -> dict:
    """Bring a station back as the part's current revision (a mesh; the script survives underneath).

    Returns ``{"version", "grew_mm"}`` — ``grew_mm`` names every side where the new shape reaches past
    where the part used to be, so a box that drops onto its frame is said out loud, not discovered.
    """
    rec = load_run(store, wid)
    if rec is None:
        raise FileNotFoundError(f"no whittle run {wid!r}")
    path = station_path(store, wid, index)
    if not os.path.exists(path):
        raise FileNotFoundError(f"run {wid} has no station {index}")
    st = next((s for s in rec["stations"] if s["index"] == int(index)), {})
    with open(path, "rb") as f:
        stl = f.read()
    before = _mesh_of(store.part_stl(rec["part"])).bounds
    grew = growth(before, _mesh_of(stl).bounds)
    removed = st.get("removed_part", st.get("removed", 0)) or 0
    version = store.write_mesh_part(
        rec["part"], stl, action="whittle",
        feedback=f"whittle {rec['kind']} station {index} ({removed:.0%} of the part removed)",
        extra={"whittle_run": wid, "station": int(index), "metrics": st.get("metrics", {}),
               "derived": st.get("derived", {}), **({"grew_mm": grew} if grew else {})})
    return {"version": version, "grew_mm": grew}
