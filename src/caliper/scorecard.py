"""CALI-47 — the scorecard: every requirement as a measured check or an objective, and how far to trust it.

The design ⇄ optimize ⇄ make loop (``specs/caliper-make-loop-spec.md``) is judged against one thing: a
card that says, for the design as it stands, whether each **check** holds (with its margin) and where each
**objective** is (with its change since the last card) — across the quadfecta: design, optimization
(strength, mass, drag), manufacturability, and cost & waste. Every number carries how far to trust it:

- ``measured`` — exact geometry (assertions, clearances, what fits);
- ``model`` — a linear frame model, on the safe side;
- ``rough`` — whittle's drag model (ranks shapes well, totals ±30%), or material data that's a guess;
- ``guess`` — prices.

What to check and push on lives in ``designs/<slug>/scorecard.yaml`` — the user's constraints in their own
words, compiled to metrics, plus settings (payload, how to score drag). The design's own assertions and
every part's ``keeps()`` are checks without being listed. Each card is filed under ``scorecards/`` with the
part versions it scored, so the next one can say what changed and whether it's out of date.
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Callable, Optional

from . import construction as C
from . import materials as M
from .design import DesignStore

GOALS = "scorecard.yaml"
LB = 0.224809                      # lbf per N


def goals_path(store: DesignStore) -> str:
    return os.path.join(store.root, GOALS)


def read_goals(store: DesignStore) -> dict:
    import yaml

    path = goals_path(store)
    if not os.path.exists(path):
        return {"settings": {}, "checks": [], "objectives": []}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return {"settings": data.get("settings") or {}, "checks": data.get("checks") or [],
            "objectives": data.get("objectives") or [], "notes": data.get("notes") or []}


def cards_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "scorecards")


def list_cards(store: DesignStore, limit: int = 20) -> list[dict]:
    root = cards_dir(store)
    if not os.path.isdir(root):
        return []
    out = []
    for name in sorted(os.listdir(root), reverse=True)[:limit]:
        with open(os.path.join(root, name)) as f:
            out.append(json.load(f))
    return out


def _metric(metrics: dict, name: str, value, unit: str, label: str, trust: str, source: str, **extra):
    metrics[name] = {"value": value, "unit": unit, "label": label, "trust": trust, "source": source, **extra}


# ---------------------------------------------------------------------------
# Cost & waste
# ---------------------------------------------------------------------------
def _sheet_price(material: str, thickness: float, stock_mm) -> float:
    P = M.PRICES
    exact = P["sheet"].get((material, round(float(thickness), 3)))
    if exact is not None:
        return exact
    area = stock_mm[0] * stock_mm[1] * 1e-6
    return P["sheet_per_m2"].get(material, 15.0) * area * float(thickness) / M.IN


def cost_and_waste(store: DesignStore, reports: dict, cutplans: dict) -> dict:
    """What the stock costs and how much of it is offcut, part by part, from each part's bill of materials
    and — for sheet goods — its cut plan's real nesting where there's a current one."""
    P = M.PRICES
    lines, waste_usd, bought_usd = [], 0.0, 0.0
    for pid, r in reports.items():
        cp = cutplans.get(pid)
        nested = {(g["material"], round(g["thickness_mm"], 3)): g for g in (cp or {}).get("sheets", [])}
        for g in r["bom"]["sheets"]:
            key = (g["material"], round(g["thickness_mm"], 3))
            if g["material"] == "steel":
                continue                    # plate is bought by weight below
            n = nested.get(key)
            count = n["sheets"] if n else g["count"]
            each = _sheet_price(g["material"], g["thickness_mm"], g["stock_mm"])
            used = n["utilisation"] if n else (g["area_mm2"] / (count * g["stock_mm"][0] * g["stock_mm"][1]) if count else 0)
            cost = count * each
            lines.append({"part": pid, "item": f"{count} × {g['label']} sheet", "usd": round(cost, 2),
                          "waste_usd": round(cost * (1 - used), 2), "waste_pct": round(1 - used, 3),
                          "from": "cut plan" if n else "bill of materials (shelf-packed)"})
            bought_usd += cost
            waste_usd += cost * (1 - used)
        for g in r["bom"]["sticks"]:
            if g["material"] == "steel":
                # tube by weight, bought cut to the foot from a metal supplier
                used_mm = g["total_mm"]
                bought_mm = math.ceil(used_mm / 304.8) * 304.8
                kg_per_mm = sum(row["mass_kg"] for row in r["pieces_raw"] if row.get("label") == g["label"]) / used_mm \
                    if used_mm else 0
                cost = bought_mm * kg_per_mm * P["steel_tube_per_kg"]
                waste = (bought_mm - used_mm) * kg_per_mm * P["steel_tube_per_kg"]
                lines.append({"part": pid, "item": f"{bought_mm / 304.8:.0f} ft of {g['label']}", "usd": round(cost, 2),
                              "waste_usd": round(waste, 2), "waste_pct": round(1 - used_mm / bought_mm, 3) if bought_mm else 0,
                              "from": "by the foot"})
            else:
                size = g["label"].split()[0]
                each = P["lumber"].get(size, 5.0)
                bought_mm = g["count"] * g["stock_len_mm"]
                cost = g["count"] * each
                waste = cost * (1 - g["total_mm"] / bought_mm) if bought_mm else 0
                lines.append({"part": pid, "item": f"{g['count']} × {g['label']} ({g['stock_len_mm'] / 304.8:g} ft)",
                              "usd": round(cost, 2), "waste_usd": round(waste, 2),
                              "waste_pct": round(1 - g["total_mm"] / bought_mm, 3) if bought_mm else 0, "from": "sticks"})
            bought_usd += cost
            waste_usd += waste
        for g in r["bom"]["coverings"]:
            cost = (g.get("canvas_yd", 0) * P["canvas_per_yd"] + g.get("cloth_yd", 0) * P["glass_cloth_per_yd"]
                    + g.get("epoxy_gal", 0) * P["epoxy_per_gal"] + g.get("glue_gal", 0) * P["glue_per_gal"]
                    + g.get("paint_gal", 0) * P["paint_per_gal"])
            lines.append({"part": pid, "item": f"{g['label']} ({g['area_ft2']} ft²)", "usd": round(cost, 2),
                          "waste_usd": 0.0, "waste_pct": 0.0, "from": "by area"})
            bought_usd += cost
        fx = r["bom"].get("fasteners")
        if fx:
            cost = fx["screws"] * P["screw_each"] + P["wood_glue_8oz"] * max(1, round(fx["glue_ml"] / 236 + 0.49))
            lines.append({"part": pid, "item": f"{fx['screws']} × {fx['screw']} and {fx['glue']}", "usd": round(cost, 2),
                          "waste_usd": 0.0, "waste_pct": 0.0, "from": "by joint length"})
            bought_usd += cost
        for g in r["bom"].get("printed") or []:               # filament by weight (CALI-48)
            cost = g["filament_g"] / 1000 * M.printed(g["material"])["usd_per_kg"]
            lines.append({"part": pid, "item": f"{g['filament_g']:.0f} g of {g['label']} filament", "usd": round(cost, 2),
                          "waste_usd": 0.0, "waste_pct": 0.0, "from": "by weight"})
            bought_usd += cost
        for row in r["pieces_raw"]:
            if row["kind"] != "lump":
                continue
            if "plate" in (row.get("label") or ""):
                cost = row["mass_kg"] * P["steel_plate_per_kg"]
                item = f"{row['label']}: {row['name']} ({row['mass_kg']:.1f} kg)"
            else:
                cost, item = P["hardware_allowance"], f"{row['label']} (allowance)"
            lines.append({"part": pid, "item": item, "usd": round(cost, 2), "waste_usd": 0.0, "waste_pct": 0.0,
                          "from": "by weight" if "plate" in (row.get("label") or "") else "allowance"})
            bought_usd += cost
    total = sum(x["usd"] for x in lines)
    return {"usd": round(total, 2), "waste_usd": round(waste_usd, 2),
            "waste_pct": round(waste_usd / bought_usd, 3) if bought_usd else 0.0, "lines": lines,
            "basis": P["basis"]}


# ---------------------------------------------------------------------------
# The card
# ---------------------------------------------------------------------------
def compute(store: DesignStore, emit: Optional[Callable] = None) -> dict:
    """Score the design as it stands, file the card, and return it."""
    from . import aero, cutplan, frame_study

    emit = emit or (lambda *a, **k: None)
    g = read_goals(store)
    settings = g["settings"]
    payload = float(settings.get("payload_lb", 0.0))
    metrics: dict = {}
    checks: list[dict] = []
    versions = {p.id: p.version for p in store.design.parts}

    # design: the assembly's own rules, measured exactly
    emit("checking", "the design's rules")
    report, _ = store.evaluate(tolerant=True)
    for res in report.results:
        checks.append({"id": f"rule:{res.id}", "label": res.expr, "status": res.status, "value": res.actual,
                       "margin": res.margin, "trust": "measured", "kind": "design", "auto": True})

    # what each part is built from: weight, keeps, the bill of materials
    emit("weighing", "what each part is built from")
    reports, cutplans = {}, {}
    for p in store.design.parts:
        if not store.is_scripted(p.id) or not C.declares(store.read_script(p.id)):
            continue
        r = C.report(store, p.id)
        r["pieces_raw"] = C.takeoff(C._items(C.declared(store, p.id)))
        reports[p.id] = r
        _metric(metrics, f"weight.{p.id}", r["mass_lb"], "lb", f"{p.id} weighs", "model", "construction")
        for k in r.get("keeps") or []:
            checks.append({"id": f"keeps:{p.id}.{k['name']}", "label": f"{p.id} holds the {k['name']}",
                           "status": "pass" if k["clear"] else "fail", "value": k["depth_mm"], "margin": -k["depth_mm"],
                           "trust": "measured", "kind": "design", "auto": True, "note": k.get("note", "")})
        runs = cutplan.list_runs(store, p.id)
        if runs:
            cutplans[p.id] = runs[0] if runs[0].get("version") == p.version else None
            if cutplans[p.id] is None:
                _metric(metrics, f"make.{p.id}.stale", True, "", f"{p.id}'s cut plan is for an older version",
                        "measured", "cut plan")
    b = C.balance(store, payload_lb=payload)
    _metric(metrics, "weight.total_lb", b["mass_lb"], "lb", f"everything, with {payload:g} lb aboard", "model", "balance")
    _metric(metrics, "hitch.tongue_lb", b["mass_lb"], "lb", "on the hitch's tongue, standing still", "model", "balance")
    if b.get("moment_lbin") is not None:
        _metric(metrics, "hitch.moment_lbin", b["moment_lbin"], "lb·in", "the hitch carries, standing still",
                "model", "balance")
        _metric(metrics, "hitch.arm_in", b["arm_in"], "in", "centre of gravity behind the hitch", "model", "balance")

    # optimization: the frame as it stands, carrying the design as built
    for p in store.design.parts:
        script = store.read_script(p.id) if store.is_scripted(p.id) else ""
        if "def members(" not in script or "def supports(" not in script:
            continue
        emit("frame", f"analysing {p.id}")
        a = frame_study.analyse(store, p.id, payload_lb=payload, walls=bool(settings.get("walls", True)))
        _metric(metrics, "frame.safety", a["safety"], "×", f"{p.id}'s weakest member on a ×{a['factor']:g} bump "
                f"({a['governing']['member']})", "model", "frame study")
        _metric(metrics, "frame.yield_x", round(a["safety"] * a["factor"], 2), "×",
                f"{p.id} yields at this many times its standing load", "model", "frame study")
        _metric(metrics, "frame.sag_in", a["deflection_in"], "in", f"{p.id} sags on a bump", "model", "frame study")
        _metric(metrics, "frame.steel_lb", a["mass_lb"], "lb", f"{p.id}'s tubes", "model", "frame study")
        if a.get("walls"):
            w = min(a["walls"], key=lambda w: w["safety"])
            _metric(metrics, "frame.walls_safety", w["safety"], "×", f"weakest wall ({w['name']})", "rough",
                    "frame study", note="skin and foam data are rough; PMF's a guess")
        if a.get("fixing"):
            _metric(metrics, "frame.fixing_lbf", a["fixing"]["force_lb"], "lbf", "the hardest-working fixing",
                    "model", "frame study")
        plates = C.declared(store, p.id).get("plates") or {}
        if plates:
            name, pl = min(plates.items(), key=lambda kv: kv[1]["safety"])
            _metric(metrics, "frame.gussets_safety", pl["safety"], "×", f"weakest gusset ({name})", "model",
                    "plate mode")
            _metric(metrics, "frame.weld_relief", min(x["relief"] for x in plates.values()), "",
                    "least of a corner weld's moment the plates take", "model", "plate mode")
        break

    # parked: the frame on its jacks with someone inside, and the floor under a knee (CALI-53)
    pk = settings.get("parked")
    if pk:
        from . import parked as P

        for p in store.design.parts:
            script = store.read_script(p.id) if store.is_scripted(p.id) else ""
            if "def jacks(" not in script:
                continue
            emit("parked", f"{p.id} parked on its jacks")
            r = P.run(store, p.id, person_lb=float(pk.get("person_lb", 200)), gear_lb=float(pk.get("gear_lb", 50)),
                      knee_lb=float(pk.get("knee_lb", 150)), factor=float(pk.get("factor", 1.5)),
                      walls=bool(settings.get("walls", True)))
            w = r["worst"]
            _metric(metrics, "parked.frame_safety", w["safety"], "×", f"{p.id} parked, worst {w['case']} "
                    f"({w['governing']})", "model", "parked")
            if r["walls_min"] is not None:
                _metric(metrics, "parked.walls_safety", r["walls_min"], "×", "weakest wall, parked", "rough", "parked")
            _metric(metrics, "parked.jack_lb", r["jacks_max_lb"], "lb", "the most a jack carries", "model", "parked")
            _metric(metrics, "parked.hitch_lb", r["hitch_max_lb"], "lb", "the most the hitch carries, parked",
                    "model", "parked")
            fl = r["floor"]
            _metric(metrics, "floor.mattress_safety", fl["on_mattress"]["safety"], "×",
                    f"the floor under a {r['knee_lb']:g} lb knee on the mattress ({fl['clear_span_in']} in clear span)",
                    "rough", "napkin", note="the mattress spreads a knee to ~10 in")
            _metric(metrics, "floor.bare_safety", fl["bare"]["safety"], "×",
                    f"the floor under a knee on bare {M.nominal(fl['thickness_mm'])} plywood", "rough", "napkin")
            _metric(metrics, "floor.clear_span_in", fl["clear_span_in"], "in", "the floor's widest clear span",
                    "measured", "parked")
            break

    # optimization: snow on any roof a part describes
    psf = float(settings.get("snow_psf", 0) or 0)
    if psf:
        from . import snow

        for pid in reports:
            roof = C.declared(store, pid).get("roof")
            if roof:
                sc = snow.check(roof, psf)
                _metric(metrics, "snow.safety", sc["safety"], "×", f"{pid}'s roof under {psf:g} lb/ft² of snow "
                        f"({sc['governing']})", "rough", "snow check", note="napkin mechanics, on the safe side")
                _metric(metrics, "snow.sag_in", round(sc["sag_mm"] / M.IN, 2), "in", "the roof sags under it",
                        "rough", "snow check")

    # optimization: drag, if the goals say how to score it
    drag = settings.get("drag")
    if drag and drag.get("part") in versions:
        emit("drag", f"scoring {drag['part']}'s drag")
        try:
            n = aero.drag_now(store, drag["part"], obstacles=drag.get("obstacles") or (),
                              speed_kmh=float(drag.get("speed_mph", 65)) * 1.609344)
            _metric(metrics, "drag.lbf", round(n * LB, 1), "lbf", f"{drag['part']}'s drag at {drag.get('speed_mph', 65)} mph",
                    "rough", "whittle drag model", note="ranks shapes well; totals ±30%")
            _metric(metrics, "drag.kwh_per_100mi", round(n * aero.KWH_PER_N_PER_100MI, 2), "kWh/100 mi",
                    "energy to push it", "rough", "whittle drag model")
        except Exception as e:                # a drag score that can't be made is reported, not fatal
            _metric(metrics, "drag.error", str(e), "", "drag couldn't be scored", "measured", "whittle")

    # manufacturability: the cut plans
    sheets = sum(gr["sheets"] for cp in cutplans.values() if cp for gr in cp["sheets"])
    missing = sum(len(gr.get("missing") or []) for cp in cutplans.values() if cp for gr in cp["sheets"])
    if any(cutplans.values()):
        _metric(metrics, "make.sheets", sheets, "sheets", "sheets to cut (current cut plans)", "measured", "cut plan")
        _metric(metrics, "make.missing", missing, "pieces", "pieces that fit no sheet", "measured", "cut plan")

    # cost & waste
    emit("cost", "pricing the stock")
    cw = cost_and_waste(store, reports, cutplans)
    _metric(metrics, "cost.usd", cw["usd"], "$", "stock to buy", "guess", "materials.PRICES", note=cw["basis"])
    _metric(metrics, "waste.usd", cw["waste_usd"], "$", "of it left as offcut", "guess", "cut plan + prices")
    _metric(metrics, "waste.pct", round(cw["waste_pct"] * 100, 1), "%", "offcut, by cost", "measured", "cut plan")

    # can your shop make it (CALI-48): every piece routed to a tool or machine you have; printing costed
    from . import making

    missing, hours, grams = [], 0.0, 0.0
    for pid in reports:
        try:
            mk = making.plan(store, pid)
        except Exception:  # noqa: BLE001 — unknown is said by the check, not a crash
            continue
        missing += [f"{pid}: {m['name']} ({m['why']})" for m in mk["missing"]]
        hours += sum(x["hours"] for x in mk["printed"])
        grams += sum(x["filament_g"] for x in mk["printed"])
    if reports:
        checks.append({"id": "make:shop", "label": "your shop can make every piece", "kind": "make", "auto": True,
                       "status": "pass" if not missing else "fail", "value": len(missing), "margin": -len(missing),
                       "trust": "measured", "note": "; ".join(missing[:6])})
        _metric(metrics, "make.not_in_shop", len(missing), "pieces", "pieces your shop can't make", "measured", "shop")
    if grams:
        _metric(metrics, "print.hours", round(hours, 1), "h", "printing time, every printed piece", "model", "slicer")
        _metric(metrics, "print.filament_g", round(grams), "g", "filament, every printed piece", "model", "slicer")

    # will it hold (CALI-54): each part's own loads(), from its strength check on this version (run if missing)
    from . import load_study

    worst = None
    for p in store.design.parts:
        if not store.is_scripted(p.id) or "def loads(" not in store.read_script(p.id):
            continue
        run = next((r for r in load_study.list_runs(store, p.id) if r.get("version") == p.version), None)
        if run is None:
            emit("strength", f"checking what {p.id} must hold")
            try:
                run = load_study.study(store, p.id)
            except Exception as e:  # noqa: BLE001 — a check that can't run is unknown, not a crash
                _metric(metrics, f"strength.{p.id}.error", str(e), "", f"{p.id}'s strength couldn't be checked",
                        "model", "strength")
                continue
        breaks = [c["breaks_lb"] for c in run["cases"] if c.get("breaks_lb")]
        if run.get("safety") is not None:
            _metric(metrics, f"strength.{p.id}.safety", run["safety"], "×", f"{p.id}, its weakest load",
                    "model", "strength check")
            worst = run["safety"] if worst is None else min(worst, run["safety"])
        if breaks:
            prev = metrics.get("strength.breaks_lb", {}).get("value")
            _metric(metrics, "strength.breaks_lb", min(breaks + ([prev] if prev else [])), "lb",
                    "the smallest predicted breaking load", "model", "strength check")
    if worst is not None:
        _metric(metrics, "strength.safety", worst, "×", "the weakest load any part must carry", "model",
                "strength check")

    # the user's checks and objectives (a proposed one is shown, and binds once it's kept: CALI-55)
    for c in g["checks"]:
        if c.get("source") == "proposed":
            m = metrics.get(c["metric"])
            checks.append({**c, "status": "proposed", "value": m["value"] if m else None, "margin": None,
                           "trust": m["trust"] if m else None, "unit": m["unit"] if m else ""})
            continue
        m = metrics.get(c["metric"])
        if m is None or not isinstance(m["value"], (int, float)):
            checks.append({**c, "status": "unknown", "value": None, "margin": None, "trust": None})
            continue
        v, lim, op = float(m["value"]), float(c["limit"]), c.get("op", ">=")
        ok = v >= lim if op == ">=" else v <= lim if op == "<=" else abs(v - lim) < 1e-9
        checks.append({**c, "status": "pass" if ok else "fail", "value": m["value"], "unit": m["unit"],
                       "margin": round(v - lim if op == ">=" else lim - v, 3), "trust": m["trust"]})
    previous = list_cards(store, 1)
    prev = previous[0]["metrics"] if previous else {}
    objectives = []
    for o in g["objectives"]:
        m = metrics.get(o["metric"])
        was = prev.get(o["metric"], {}).get("value")
        value = m["value"] if m else None
        objectives.append({**o, "value": value, "unit": m["unit"] if m else "", "trust": m["trust"] if m else None,
                           "was": was, "change": (round(value - was, 3) if isinstance(value, (int, float))
                                                  and isinstance(was, (int, float)) else None)})
    card = {"created": time.time(), "versions": versions, "settings": settings, "checks": checks,
            "notes": g.get("notes") or [],
            "objectives": objectives, "metrics": metrics, "cost": cw,
            "summary": {"pass": sum(c["status"] == "pass" for c in checks),
                        "fail": sum(c["status"] == "fail" for c in checks),
                        "unknown": sum(c["status"] not in ("pass", "fail", "proposed") for c in checks),
                        "proposed": sum(c["status"] == "proposed" for c in checks)}}
    os.makedirs(cards_dir(store), exist_ok=True)
    with open(os.path.join(cards_dir(store), time.strftime("%Y%m%d-%H%M%S") + ".json"), "w") as f:
        json.dump(card, f, indent=2, default=str)
    store.append_log({"kind": "scorecard", "action": "scored", **card["summary"]})
    emit("done", f"{card['summary']['pass']} checks pass, {card['summary']['fail']} fail")
    return card
