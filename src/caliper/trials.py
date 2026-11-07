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
    from . import load_study as L

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
            "factor": case["factor"],
            "where": plate.get("piece") if plate.get("done") else case["fea"].get("in"),
            "breaks_lb": breaks, "steps": steps, "per_lb_mm": [round(lo, 6), round(hi, 6)],
            "measure_with": measure_with(hi * case["lb"]),
            "basis": ("from an FEA too coarse to see its walls, so a rough guess until it's checked finer: "
                      if L.unresolved(run, case) else "")                       # said, not hidden (CALI-110)
                     + "linear to breaking: the FEA's sag (joints solid, the stiff end)"
                     + (" to the plate check's (edges free, the flexible end)" if flex is not None else "")}


def record(store: DesignStore, part_id: str, load_lb: float, sag_mm: Optional[float] = None,
           broke: bool = False, note: str = "") -> dict:
    """Keep one step of a real test."""
    entry = store.design.part(part_id)
    if entry is None:
        raise KeyError(f"no part {part_id!r}")
    if not _real(load_lb):
        raise ValueError("how much was on it? (a number of lb, more than nothing)")
    if sag_mm is not None and not _real(sag_mm):
        raise ValueError("how far did it sag? (a number of mm, more than nothing; leave it out if you didn't measure)")
    row = {"at": time.time(), "version": entry.version, "load_lb": float(load_lb),
           "sag_mm": None if sag_mm is None else float(sag_mm), "broke": bool(broke), "note": note.strip()}
    p = path(store, part_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(row) + "\n")
    store.append_log({"kind": "trial", "action": "recorded", "part": part_id, "load_lb": row["load_lb"],
                      "broke": row["broke"]})
    return row


def _real(x) -> bool:
    """A measurement: a finite number more than nothing (NaN gets past ``x <= 0``; a string or true isn't a
    number, CALI-86)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def _row(line: str) -> Optional[dict]:
    """One step from the file, or None if it isn't one (a hand-edited line, a NaN)."""
    try:
        r = json.loads(line)
    except ValueError:
        return None
    if not isinstance(r, dict) or not _real(r.get("load_lb")) or (r.get("sag_mm") is not None
                                                                  and not _real(r["sag_mm"])):
        return None
    if not isinstance(r.get("version"), int) or isinstance(r.get("version"), bool) \
            or not isinstance(r.get("broke", False), bool):
        return None                                 # every field a step is read by, as record() writes it
    return r


def _read(store: DesignStore, part_id: str) -> tuple[list[dict], int]:
    """The steps on file, and how many lines were skipped as not steps."""
    try:
        with open(path(store, part_id)) as f:
            lines = [line for line in f if line.strip()]
    except OSError:
        return [], 0
    got = [_row(line) for line in lines]
    return [r for r in got if r is not None], sum(r is None for r in got)


def rows(store: DesignStore, part_id: str) -> list[dict]:
    return _read(store, part_id)[0]


def compared(store: DesignStore, part_id: str) -> dict:
    """The prediction and the record side by side: each step with what it should have sagged, and a verdict."""
    pred = predict(store, part_id)
    entry = store.design.part(part_id)
    out = []
    kept, skipped = _read(store, part_id)
    for r in kept:
        row = {**r, "stale": entry is not None and r["version"] != entry.version}
        if pred and not row["stale"]:
            lo, hi = pred["per_lb_mm"]
            row["predicted_mm"] = [round(lo * r["load_lb"], 3), round(hi * r["load_lb"], 3)]
            if r.get("sag_mm") is not None and hi > 0:
                mid = math.sqrt(lo * hi) * r["load_lb"] if lo > 0 else hi * r["load_lb"]
                row["ratio"] = round(r["sag_mm"] / mid, 2)          # against the middle of the range
        out.append(row)
    got = {"prediction": pred, "rows": out, "skipped": skipped}
    if skipped:
        got["skipped_note"] = (f"{skipped} line{'s' if skipped > 1 else ''} in {os.path.basename(path(store, part_id))} "
                               f"weren't a test step (a number that isn't one, or not JSON) and were left out")
    return got


#: A break this close to the predicted load counts as matching the prediction (the foreman's band, #71 rework).
MATCHES = 0.9
#: A sag more than this many times outside the predicted range is one the model doesn't fit.
SAG_OUT = 2.0


def _times_over(factor: float) -> str:
    return "twice over" if factor == 2 else f"{factor:g} times over"


def summary(store: DesignStore, part_id: str, inches: bool = True) -> Optional[dict]:
    """The card's line: where it broke, judged against what it must hold and what we predicted; or the heaviest load
    it held, with the worst-fitting sag of every step that has one (CALI-86: each step judged, the worst governs)."""
    got = compared(store, part_id)
    live = [r for r in got["rows"] if not r["stale"]]
    if not live:
        return None
    pred = got["prediction"] or {}
    must = pred["lb"] * pred.get("factor", 1.0) if pred.get("lb") else None
    broke = min((r for r in live if r["broke"]), key=lambda r: r["load_lb"], default=None)
    if broke:
        at, breaks = broke["load_lb"], pred.get("breaks_lb")
        if must and at < must:                              # a fail, whatever was predicted (rule 6)
            return {"text": f"It broke at {at:,.0f} lb in your test. We predicted it would hold {must:,.0f}.",
                    "status": "bad", "broke": True}
        if breaks and at < MATCHES * breaks:
            held = (f" It still held the {must:,.0f} lb it must hold ({pred['lb']:g} lb, "
                    f"{_times_over(pred.get('factor', 1.0))} for {pred.get('case', 'its load').lower()})." if must else "")
            return {"text": f"It broke sooner than we predicted, so our check was too hopeful.{held} "
                            f"(It broke at {at:,.0f} lb; we predicted about {breaks:,.0f}.)",
                    "status": "warn", "broke": True}
        said = f"Tested: it broke at {at:,.0f} lb" + (f", as we predicted (about {breaks:,.0f})" if breaks else "")
        return {"text": said + ".", "status": "ok" if breaks else "info", "broke": True}
    top = max(live, key=lambda r: r["load_lb"])
    # held, but short of what it must hold: not a pass for it (#132 review)
    short = bool(must) and top["load_lb"] < must
    said, status = (f"Tested: it held {top['load_lb']:,.0f} lb" + (f", short of the {must:,.0f} lb it must hold: "
                    "test it to there before anyone relies on it" if short else "")), ("warn" if short else "ok")
    worst, how = None, 1.0                                   # the step whose sag fits the prediction worst
    for r in live:
        if r.get("sag_mm") is None or not r.get("predicted_mm"):
            continue
        a, b = r["predicted_mm"]
        out = max(r["sag_mm"] / b if b > 0 else 1.0, a / r["sag_mm"] if r["sag_mm"] > 0 else 1.0)
        if worst is None or out > how:
            worst, how = r, out
    if worst is not None:
        a, b = worst["predicted_mm"]
        step = f"at {worst['load_lb']:,.0f} lb it sagged {_sag(worst['sag_mm'], inches)} " \
               f"(we predicted {_sag(a, inches, unit=False)}–{_sag(b, inches)})"
        if worst["sag_mm"] > SAG_OUT * b:
            said, status = f"{said}, but {step}: it sagged more than we predicted", "warn"
        elif worst["sag_mm"] < a / SAG_OUT:
            said, status = f"{said}, but {step}: it sagged less than we predicted, so it's stiffer than our check said", "warn"
        else:
            said += f"; {step}"
    return {"text": said + ".", "status": status, "broke": False}


def _sag(mm: float, inches: bool, unit: bool = True) -> str:
    if inches:
        return f"{mm / IN:.3f}" + (" in" if unit else "")
    return f"{mm:.2f}" + (" mm" if unit else "")
