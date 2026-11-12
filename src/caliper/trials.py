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


#: A 0.001 in dial indicator's smallest division, and the thinnest feeler gauge in a usual set (about 0.0015 in), mm.
DIAL_MM, FEELER_MM = 0.025, 0.04


def measure_with(sag_mm: float, closed: bool = False, across: str = "the two held edges") -> str:
    """What will see a sag this big, on this part. ``closed``: its underside is shut in, so it's measured from above, off
    a straightedge on the edges that don't move (``across``), and beside the foot, because the load sits where it would cross
    (#70 item 2)."""
    feeler = sag_mm >= 2 * FEELER_MM                 # the thinnest blade with something to spare
    if sag_mm < DIAL_MM:
        return "no hand tool: this sag is under what a dial indicator reads, so the test is the load held"
    if closed:
        if sag_mm < 0.5:
            return (f"a dial indicator on a straightedge across {across}, read beside the foot"
                    + (" (or feeler gauges under the straightedge)" if feeler else "")
                    + ": its underside is closed in, so it can't be read from below")
        return f"a straightedge across {across} and a steel rule, read beside the foot: its underside is closed in"
    if sag_mm < 0.5:
        return ("a dial indicator under the middle" + (" (or a straightedge across the top and feeler gauges)" if feeler else "")
                + ": a tape measure won't see a sag this small")
    if sag_mm < 3:
        return "a straightedge across the top and a steel rule or feeler gauges at the middle"
    return "a tape measure from the floor to the middle of the top, before and with the load"


def closed_under(store, part_id: str, case: dict, plate: dict) -> bool:
    """Whether the underside of the panel the load lands on is shut in: from just below the load's middle, something of
    the part stands in the way in all four directions. A panel without a plate check has nothing to say it's closed."""
    if not (plate or {}).get("done") or not case.get("lo"):
        return False
    import numpy as np

    from . import spatial

    try:
        mesh = store.part_geometry(part_id).require_mesh()
    except Exception:  # noqa: BLE001 — a part that can't say: read from below, as before
        return False
    lo, hi = np.asarray(case["lo"], float), np.asarray(case["hi"], float)
    at = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2] - plate["thickness_mm"] - 5.0]
    ways = np.array([(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)])
    _, rays, _ = spatial.intersects_location(mesh, np.array([at] * 4, float), ways)
    return len(set(rays.tolist())) == 4


#: Odd terms of the plate series each way: past this the sample top's falloff moves under 0.1%.
SERIES = 39


def _navier(a: float, b: float, foot: float, x: float, y: float) -> float:
    """An ``a`` × ``b`` plate's sag at (x, y), simply supported all round, under a ``foot``-square patch at its middle: Navier's
    double sine series (Timoshenko & Woinowsky-Krieger §30), up to the plate's stiffness and the load, which a share cancels."""
    def spread(z: float) -> float:                           # the patch's share of a term: sin z / z, a point load's 1
        return math.sin(z) / z if z else 1.0

    total = 0.0
    for m in range(1, 2 * SERIES, 2):
        for n in range(1, 2 * SERIES, 2):
            pm, pn = m * math.pi, n * math.pi
            total += (math.sin(pm / 2) * math.sin(pn / 2) * spread(pm * foot / (2 * a)) * spread(pn * foot / (2 * b))
                      * math.sin(pm * x / a) * math.sin(pn * y / b) / ((m / a) ** 2 + (n / b) ** 2) ** 2)
    return total


def beside_the_foot(plate: dict, along: str = "long") -> float:
    """A panel's sag half an inch past the foot's edge, as a share of its sag under the foot (#70 item 2, #228 review). Held all
    round, from the plate series: ``along`` the long side (a straightedge resting on the two long edges, read toward a short end)
    or the short. The sample top, 368 × 216 mm under a 100 mm foot: 0.78 along the long side, 0.59 along the short. On two
    edges the straightedge moves along the held edges with the foot: 1."""
    if plate.get("as") == "beam":
        return 1.0
    a, b = plate["a_mm"], plate["b_mm"]                       # long, short
    foot = max(plate.get("footprint_mm") or [0.0])           # a square foot its widest way: a round or square foot near enough
    off = foot / 2 + IN / 2
    x, y = (a / 2 + off, b / 2) if along == "long" else (a / 2, b / 2 + off)
    if x >= a or y >= b:
        return 0.0                                            # past the held edge: it doesn't move there
    return _navier(a, b, foot, x, y) / _navier(a, b, foot, a / 2, b / 2)


#: the most steps a test plan has, whatever it's asked to reach (#202: 66 million, from a check that saw no stress, held up the card)
MOST_STEPS = 40


def _plate_material(store: DesignStore, part_id: str, piece: Optional[str]) -> Optional[dict]:
    """The plate-checked piece's own material, as the strength check reads one (its grain ratio): a part of two
    materials records its main one, and the bar stool's plywood seat sits on PETG (#209 review, round 3)."""
    if not piece:
        return None
    from . import construction as C
    from . import load_study as L

    try:
        item = next((it for it in C.declared(store, part_id).get("construction") or []
                     if isinstance(it, dict) and it.get("name") == piece and it.get("material")), None)
        return L.material([{"material": item["material"], "volume": 1.0}]) if item else None
    except Exception:  # noqa: BLE001 — a part that can't say: the run's own material, as before
        return None


def predict(store: DesignStore, part_id: str) -> Optional[dict]:
    """For the worst load the part was checked for: the sag at each step to where it should break, as a range,
    and what to measure it with. None without a strength check on this version."""
    from . import answers, load_study as L

    run = _run(store, part_id)
    if run is None:
        return None
    cases = [c for c in run["cases"] if c.get("safety") is not None and c.get("fea", {}).get("supported") and not L.blind(run, c)]   # #202
    if not cases:
        return None
    case = min(cases, key=lambda c: c["safety"])
    applied = case["lb"] * case["factor"]                      # what the check put on it
    stiff = case["fea"]["deflection_mm"] / applied             # mm per lb, the FEA: joints solid
    plate = case.get("plate") or {}
    # the plate or beam's sag: the declared grain's where a piece says which way it runs ("grain": "along" or
    # "across" the span), else the worse grain's, so the prediction spans both (#122 review)
    grain = plate.get("grain") if plate.get("grain") in ("along", "across") else None
    sag = plate.get(f"deflection_{grain}_mm") if grain else None
    weaker = False
    if sag is None and plate.get("done") and plate.get("as") != "beam":
        # a plate held all round writes its sag at the material's E, along the face grain, while its strength is
        # taken across it: its sag across the grain, the weaker way, as its strength is (#209 review)
        mat = _plate_material(store, part_id, plate.get("piece")) or run.get("material") or {}
        ratio = (mat["E_across"] / mat["E"]) if mat.get("E_across") and mat.get("E") else mat.get("across", 1.0)
        sag = plate.get("deflection_across_mm") or plate["deflection_mm"] / min(max(float(ratio), 1e-6), 1.0)
        weaker = ratio < 1.0
    flex = (sag if sag is not None else plate["deflection_mm"]) / applied if plate.get("done") else None
    lo, hi = sorted([stiff, flex if flex is not None else stiff])
    closed = closed_under(store, part_id, case, plate)
    spot = beside_the_foot(plate) if closed else 1.0           # where it can be read: the prediction is for there (#70 item 2)
    all_round = closed and plate.get("as") != "beam"           # held all round: say which way the straightedge goes
    lo, hi = lo * spot, hi * spot
    span = L.fixed_ends(run, case)                             # not settled: nothing to load it up to (CALI-153)
    unknown = L.unresolved(run, case)
    gap = L.unseen(run, case) if unknown else ""                # another check governs; the FEA couldn't see a wall (#248)
    breaks = None if unknown or span else case.get("breaks_lb")     # a plan isn't built up to a number nobody can read (#202)
    top = breaks or applied * 2
    step = 50 if top <= 1500 else 100                          # a sandbag at a time
    step = max(step, math.ceil(top / MOST_STEPS / step) * step)   # and a plan a person could carry out
    # up to where it should break, no further: a stool predicted to go at 220 lb doesn't need 250 on it
    loads = sorted({x for x in {case["lb"], *range(step, int(breaks), step), math.ceil(breaks)} if x <= math.ceil(breaks)} if breaks
                   else {case["lb"], *(x for x in range(step, int(applied) + 1, step))} if span       # no further than it must carry (CALI-153)
                   else {case["lb"], *range(step, int(applied * 2) + step, step)})
    steps = [{"lb": lb, "sag_mm": [round(lo * lb, 3), round(hi * lb, 3)]} for lb in loads]
    return {"part": part_id, "version": run["version"], "run": run["id"], "case": case["name"], "lb": case["lb"],
            "factor": case["factor"],
            "where": plate.get("piece") if plate.get("done") else L.peak_in(case["fea"]),   # not an old label
            "breaks_lb": breaks,                                        # None: not a number to test against (#191 review)
            "steps": steps, "per_lb_mm": [round(lo, 6), round(hi, 6)],
            "measure_with": measure_with(hi * case["lb"], closed, across="the two long edges" if all_round else "the two held edges"),
            "closed_under": closed, "spot": round(spot, 3),
            "measured_at": (("half an inch past the foot toward a short end, from a straightedge resting on the two long edges"
                             if all_round else "beside the foot, half an inch off its edge, from a straightedge on the held edges")
                            if closed else "at the middle"),
            # held all round, a straightedge fits either way and the two readings differ by a third (#228 review): the
            # sag is given for the long edges, and this says what the other way reads
            "other_way": (f"Laid on the short edges and read half an inch past the foot toward a long edge, it sags about "
                          f"{beside_the_foot(plate, 'short') / spot:.0%} of that." if all_round and spot else None),
            # its safety as the card says it, against the same thing (#64 item 9); not a number to test against
            # where the break isn't settled
            "why_no_break": ("the check holds it fixed where it's held, so it may read too strong" if span else
                             f"no prediction: the check couldn't see the wall: {gap}" if gap else
                             "no prediction: the check was too coarse to see its walls" if unknown else None),
            "over": None if unknown or span else answers.over(case, run.get("min_safety")),
            "basis": ("from checks that couldn't see every wall, so a rough guess until it's checked again: " if gap else
                      "from an FEA too coarse to see its walls, so a rough guess until it's checked finer: "
                      if unknown else "from an FEA that holds it fixed where it's held, so a real one may give more: "
                      if span else "")                       # said, not hidden (CALI-110)
                     + "linear to breaking: the FEA's sag (joints solid, the stiff end)"
                     + ((" to the beam check's (resting on two edges, free to turn: the flexible end)" if plate.get("as") == "beam"
                         else " to the plate check's (held all round, edges free to turn"
                        + (", the grain taken the weaker way, as its strength is" if weaker else "")
                        + ": the flexible end)")   # (#64 item 7, #209 review)
                        if flex is not None else "")
                     + (f", given beside where the foot is: about {spot:.0%} of its sag under the foot (rough: a beam's curve along "
                        f"the panel)" if closed and spot < 1.0 else "")}


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
            # what it had to hold is the load times its factor, not the prediction; the prediction is the number
            # #42's calibration needs, so it's said too, or that it wasn't settled (CALI-88, #64 item 13)
            had = (f"It had to hold {must:,.0f} ({pred['lb']:g} lb, {_times_over(pred.get('factor', 1.0))} for "
                   f"{pred.get('case', 'its load').lower()})")
            return {"text": f"It broke at {at:,.0f} lb in your test. {had}"
                            + (f", and we predicted about {breaks:,.0f}." if breaks else
                               "; where it would break wasn't settled."),
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
               f"(we predicted {sag_range(a, b, inches)})"
        if worst["sag_mm"] > SAG_OUT * b:
            said, status = f"{said}, but {step}: it sagged more than we predicted", "warn"
        elif worst["sag_mm"] < a / SAG_OUT:
            said, status = f"{said}, but {step}: it sagged less than we predicted, so it's stiffer than our check said", "warn"
        else:
            said += f"; {step}"
    return {"text": said + ".", "status": status, "broke": False}


def sag_range(a: float, b: float, inches: bool) -> str:
    """A predicted sag's two ends, to enough places that they differ (the page's ``sagRange``, op for op: #70 item 2)."""
    x, y, unit = (a / IN, b / IN, " in") if inches else (a, b, " mm")
    places = 3 if inches else 2
    if x == y:
        return f"{x:.{places}f}{unit}"
    while places < 6 and f"{x:.{places}f}" == f"{y:.{places}f}":
        places += 1
    return f"{x:.{places}f}–{y:.{places}f}{unit}"


def _sag(mm: float, inches: bool, unit: bool = True) -> str:
    if inches:
        return f"{mm / IN:.3f}" + (" in" if unit else "")
    return f"{mm:.2f}" + (" mm" if unit else "")
