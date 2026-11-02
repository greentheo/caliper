"""CALI-80 (#48) — record the test: what the strength check predicted, against what the real one did.

Showcase 1 ends with Dad standing on the stool, then sandbags going on until it breaks. Each load step is a
measurement worth keeping: how far the top sagged, and whether (and when) it broke. Set beside the prediction,
that is the first real point for calibrating the strength check (#42).

**The prediction** comes from the latest strength check on the part as it is: for each load, the sag at the
middle of the panel it's put on, linear in the load until it breaks, as a range. The FEA's sag is the stiff
end (it takes the joints as solid wood); the plate check's, where it was done on that panel, the flexible end
(edges free to turn). Where it should break is the check's ``breaks_lb``. It also says what will see a sag
that small: a stool's top under Dad sags a few thousandths of an inch, which a tape measure won't show.

**The record** is kept with the design, one line per step (``trials/<part>.jsonl``), with the version it was
made on, so a test of an older version reads as one.
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Optional

from .design import DesignStore

IN = 25.4


def path(store: DesignStore, part_id: str) -> str:
    return os.path.join(store.root, "trials", f"{part_id}.jsonl")


def _run(store: DesignStore, part_id: str) -> Optional[dict]:
    from . import load_study as L

    entry = store.design.part(part_id)
    runs = [r for r in L.list_runs(store, part_id) if entry and r.get("version") == entry.version]
    return runs[0] if runs else None


def measure_with(sag_mm: float) -> str:
    """What will see a sag this big."""
    if sag_mm < 0.5:
        return ("a dial indicator under the middle (or a straightedge across the top and feeler gauges): "
                "a tape measure won't see a sag this small")
    if sag_mm < 3:
        return "a straightedge across the top and a steel rule or feeler gauges at the middle"
    return "a tape measure from the floor to the middle of the top, before and with the load"


def predict(store: DesignStore, part_id: str) -> Optional[dict]:
    """For the worst load the part was checked for: the sag at each step to where it should break, as a range,
    and what to measure it with. None without a strength check on this version."""
    run = _run(store, part_id)
    if run is None:
        return None
    cases = [c for c in run["cases"] if c.get("safety") is not None and c.get("fea", {}).get("supported")]
    if not cases:
        return None
    case = min(cases, key=lambda c: c["safety"])
    applied = case["lb"] * case["factor"]                      # what the check put on it
    stiff = case["fea"]["deflection_mm"] / applied             # mm per lb, the FEA: joints solid
    plate = case.get("plate") or {}
    flex = plate["deflection_mm"] / applied if plate.get("done") else None
    lo, hi = sorted([stiff, flex if flex is not None else stiff])
    breaks = case.get("breaks_lb")
    step = 50 if (breaks or applied) <= 1500 else 100          # a sandbag at a time
    loads = sorted({case["lb"], *range(step, int(breaks or applied * 2) + step, step)})
    steps = [{"lb": lb, "sag_mm": [round(lo * lb, 3), round(hi * lb, 3)]} for lb in loads]
    return {"part": part_id, "version": run["version"], "run": run["id"], "case": case["name"], "lb": case["lb"],
            "where": plate.get("piece") if plate.get("done") else case["fea"].get("in"),
            "breaks_lb": breaks, "steps": steps, "per_lb_mm": [round(lo, 6), round(hi, 6)],
            "measure_with": measure_with(hi * case["lb"]),
            "basis": "linear to breaking: the FEA's sag (joints solid, the stiff end)"
                     + (" to the plate check's (edges free, the flexible end)" if flex is not None else "")}


def record(store: DesignStore, part_id: str, load_lb: float, sag_mm: Optional[float] = None,
           broke: bool = False, note: str = "") -> dict:
    """Keep one step of a real test."""
    entry = store.design.part(part_id)
    if entry is None:
        raise KeyError(f"no part {part_id!r}")
    if not load_lb or load_lb <= 0:
        raise ValueError("how much was on it? (in lb)")
    row = {"at": time.time(), "version": entry.version, "load_lb": float(load_lb),
           "sag_mm": None if sag_mm is None else float(sag_mm), "broke": bool(broke), "note": note.strip()}
    p = path(store, part_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(row) + "\n")
    store.append_log({"kind": "trial", "action": "recorded", "part": part_id, "load_lb": row["load_lb"],
                      "broke": row["broke"]})
    return row


def rows(store: DesignStore, part_id: str) -> list[dict]:
    try:
        with open(path(store, part_id)) as f:
            return [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return []


def compared(store: DesignStore, part_id: str) -> dict:
    """The prediction and the record side by side: each step with what it should have sagged, and a verdict."""
    pred = predict(store, part_id)
    entry = store.design.part(part_id)
    out = []
    for r in rows(store, part_id):
        row = {**r, "stale": entry is not None and r["version"] != entry.version}
        if pred and not row["stale"]:
            lo, hi = pred["per_lb_mm"]
            row["predicted_mm"] = [round(lo * r["load_lb"], 3), round(hi * r["load_lb"], 3)]
            if r.get("sag_mm") is not None and hi > 0:
                mid = math.sqrt(lo * hi) * r["load_lb"] if lo > 0 else hi * r["load_lb"]
                row["ratio"] = round(r["sag_mm"] / mid, 2)          # against the middle of the range
        out.append(row)
    return {"prediction": pred, "rows": out}


def summary(store: DesignStore, part_id: str, inches: bool = True) -> Optional[dict]:
    """The card's line: the heaviest load it held (and its sag against the prediction), or where it broke."""
    got = compared(store, part_id)
    live = [r for r in got["rows"] if not r["stale"]]
    if not live:
        return None
    pred = got["prediction"] or {}
    broke = next((r for r in live if r["broke"]), None)
    if broke:
        said = f"Tested: it broke at {broke['load_lb']:,.0f} lb"
        if pred.get("breaks_lb"):
            said += f" (we predicted about {pred['breaks_lb']:,.0f})"
        return {"text": said + ".", "status": "info", "broke": True}
    top = max(live, key=lambda r: r["load_lb"])
    said = f"Tested: it held {top['load_lb']:,.0f} lb"
    if top.get("sag_mm") is not None:
        said += f", sagging {_sag(top['sag_mm'], inches)}"
        if top.get("predicted_mm"):
            a, b = top["predicted_mm"]
            said += f" (we predicted {_sag(a, inches, unit=False)}–{_sag(b, inches)})"
    return {"text": said + ".", "status": "ok", "broke": False}


def _sag(mm: float, inches: bool, unit: bool = True) -> str:
    if inches:
        return f"{mm / IN:.3f}" + (" in" if unit else "")
    return f"{mm:.2f}" + (" mm" if unit else "")
