"""The four questions, answered in a line anyone can read (``specs/caliper-four-questions-spec.md``, step 1).

What is it? Will it work? What do I buy? How do I make it? Each card's top line is the answer: a verdict and
the one or two numbers that carry it, in the person's units, never an internal name. The numbers behind it
(today's panels) open beneath it in the app. A card with nothing to say yet says what to tell Caliper.

Every line comes from what's already measured: the part's description and size, its strength check and
rules, the scorecard, what it's built from and what that costs, how the shop makes it. A card never runs a
study to draw itself. A verdict from an older version says so.
"""

from __future__ import annotations

from typing import Optional

from . import construction as C
from .design import DesignStore

IN = 25.4
#: Card status, worst first: something fails, something isn't checked yet, all good, just information.
ORDER = ("bad", "warn", "ok", "info")
#: What a strength verdict promises and what it doesn't (CALI-59), said wherever one is shown.
PROMISE = ("A prediction, not a certificate: it rests on the loads it was given and on textbook strengths for "
           "the material. Real wood varies and so do joints, so test it gently before you trust it with a person.")


def _len(mm: float, inches: bool) -> str:
    return f"{mm / IN:.1f} in".replace(".0 in", " in") if inches else f"{mm:.0f} mm"


def _times(x: float) -> str:
    """3.1 -> "3 times over"; the kid's reading of a safety factor."""
    n = round(x, 1)
    return f"{n:g} times over" if n < 10 else "more than 10 times over"


def _sentence(text: str, most: int = 120) -> str:
    """The first sentence, ending in a full stop, for a top line: a description can be a paragraph of build
    instructions."""
    first = (text or "").strip().split(". ")[0].rstrip(".")
    if len(first) <= most:
        return first + "."
    # cut where a phrase ends ("…, built from five panels (two sides, …" -> "…, built from five panels…")
    for sep in (" (", " — ", "; ", ", "):                   # an aside first, then a clause
        cut = first.rfind(sep, 0, most - 1)
        if cut > most // 2:
            return first[:cut].rstrip(",;") + "…"
    return first[:most - 1].rsplit(" ", 1)[0].rstrip(",;") + "…"


def _worst(lines: list[dict]) -> str:
    return min((ln["status"] for ln in lines), key=ORDER.index, default="info")


def _card(key: str, q: str, lines: list[dict], hint: str = "") -> dict:
    card = {"key": key, "q": q, "status": _worst(lines) if lines else "info", "lines": lines, "hint": hint}
    if any(ln.get("study") in ("load", "frame") and ln["status"] in ("ok", "bad") for ln in lines):
        card["promise"] = PROMISE
    return card


def _line(text: str, status: str = "info", **kw) -> dict:
    return {"text": text, "status": status, **kw}


# ---------------------------------------------------------------------------
# One part
# ---------------------------------------------------------------------------
def part(store: DesignStore, state: dict, pid: str) -> list[dict]:
    from . import load_study, making

    p = next(x for x in state["parts"] if x["id"] == pid)
    inches = state.get("display_units", "in") == "in"
    report = None
    if p.get("built"):
        try:
            report = C.report(store, pid)
        except Exception:  # noqa: BLE001 — the card says what it can without it
            report = None

    # What is it?
    what = [_line(_sentence(p.get("intent") or pid))]
    if p.get("bbox"):
        x, y, z = p["bbox"]["size"]
        a, b = max(x, y), min(x, y)
        bom = (report or {}).get("bom") or {}
        made = ", ".join(dict.fromkeys(g["label"] for g in bom.get("sheets", []) + bom.get("sticks", [])
                                       + bom.get("printed", []))) if report else ""
        what.append(_line(f"{_len(a, inches)[:-3]} × {_len(b, inches)}, {_len(z, inches)} tall"
                          + (f", from {made}" if made else "") + "."))
    else:
        what.append(_line("It won't build right now: say what's wrong with it, or roll it back.", "bad"))
    if report:
        # its shape and its pieces disagree (CALI-83: a stool built as a filled box): every study reads one or the other
        try:
            from . import consistency

            off = sorted((r for r in consistency.check(C.declared(store, pid), store.part_geometry(pid))
                          if r.status == "fail" and r.detail), key=lambda r: r.id != "construction_volume")
        except Exception:  # noqa: BLE001 — the card says what it can
            off = []
        if off:
            what.append(_line(f"Its 3D shape and its pieces don't match: {off[0].detail}. Say \"fix its shape to "
                              f"match its pieces\" and I'll revise it.", "bad"))

    # Will it work?
    work = []
    if p.get("role") == "fixed":
        work.append(_line("It's a reference (like the car): nothing to check."))
    runs = [r for r in state.get("load_runs") or [] if r["part"] == pid]
    if runs:
        run, stale = runs[0], runs[0].get("version") != p["version"]
        for c in run["cases"]:
            if c.get("safety") is None:
                continue
            if c.get("holds"):
                text = f"Holds {c['name'].lower()}, {_times(c['safety'])}."
            else:
                text = f"Doesn't hold {c['name'].lower()}: only {_times(c['safety'])}, and it needs {run['min_safety']:g}."
            work.append(_line(text + (" (Checked on an older version: check again.)" if stale else ""),
                              "warn" if stale else "ok" if c.get("holds") else "bad", study="load"))
    elif p.get("loads"):
        failed = next((h for h in reversed(p.get("history") or []) if h.get("kind") == "load"
                       and h.get("action") == "failed" and h.get("version") == p["version"]), None)
        work.append(_line(f"I couldn't check it holds: {failed['why']}." if failed else
                          "Not checked yet whether it holds what it must: Check it holds.", "warn", study="load"))
    elif p.get("built") and p.get("role") != "fixed" and not p.get("framed"):
        work.append(_line("Not checked yet: say what it has to hold (\"it has to hold me, 200 lb\").", "warn",
                          study="load"))
    if p.get("loads") and p.get("role") != "fixed":
        from . import trials

        tried = trials.summary(store, pid, inches)            # what the real one did (CALI-80)
        if tried:
            work.append(_line(tried["text"], tried["status"], study="trial"))
    frames = [r for r in state.get("frame_runs") or [] if r["part"] == pid]
    if frames:
        d = frames[0].get("drawn") or {}
        if d.get("safety") is not None:
            ok = d["safety"] >= frames[0].get("min_safety", 0)
            work.append(_line(f"The frame holds, {_times(d['safety'])}." if ok else
                              f"The frame is too weak as drawn: {_times(d['safety'])}, it needs "
                              f"{frames[0].get('min_safety')}.", "ok" if ok else "bad", study="frame"))
    mine = {r["id"] for r in p.get("rules") or []}
    rules = [r for r in (state.get("report") or {}).get("results", []) if r.get("id") in mine]
    if len([x for x in state["parts"] if x.get("role") != "fixed"]) == 1 and p.get("role") != "fixed":
        # the only part: what the design is held to is what it's held to (the strength lines say it already)
        work += [ln for ln in held_to(state, measured(store, state)) if ln.get("study") != "load"]
    bad = [r for r in rules if r["status"] == "fail"]
    if rules:
        work.append(_line(f"Its {len(rules)} rule{'s' if len(rules) != 1 else ''} all pass." if not bad else
                          f"{len(bad)} of its rules fail: {', '.join(r['id'] for r in bad[:3])}.",
                          "ok" if not bad else "bad"))

    # What do I buy?
    buy = []
    if report:
        b = report["bom"]
        items = [f"{g['count']} sheet{'s' if g['count'] != 1 else ''} of {g['label']}" for g in b["sheets"]]
        items += [f"{g['count']} × {g['label']}" for g in b["sticks"]]
        if b.get("fasteners"):
            items.append(f"{b['fasteners']['screws']} screws and wood glue")
        items += [f"{g['filament_g']:.0f} g of {g['label'].split(' ')[0]} filament" for g in b.get("printed") or []]
        items += [g["label"].split(" (")[0].lower() for g in b["coverings"]]
        usd = _cost(store, pid, report)
        buy.append(_line(", ".join(items[:5]) + (f": about ${usd:,.0f}." if usd else ".")))
        lb = report["mass_lb"]
        buy.append(_line(f"It weighs {lb:g} lb" + (", easy for a kid to carry." if lb <= 10 else ".")))
    elif p.get("role") != "fixed":
        buy.append(_line("Not known yet: it doesn't say what it's built from. Ask for it from plywood, lumber "
                         "or tube and the designer lists the pieces.", "warn"))

    # How do I make it?
    how = []
    if report and p.get("role") != "fixed":
        try:
            mk = making.plan(store, pid)
        except Exception:  # noqa: BLE001
            mk = None
        if mk:
            tools = [t for t in mk["by_how"] if t != "printer"]
            n = sum(len(v) for k, v in mk["by_how"].items() if k != "printer")
            holes = sum(x.get("holes", 0) for x in mk["pieces"])
            if tools:
                how.append(_line(f"With {_and(['your ' + t for t in tools])}: {n} piece{'s' if n != 1 else ''}"
                                 + (f", {holes} hole{'s' if holes != 1 else ''}" if holes else "") + ".", "ok"))
            for pr in mk["printed"]:
                how.append(_line(f"Print it in {pr['material'].upper()}: {pr['pieces']} piece"
                                 f"{'s' if pr['pieces'] != 1 else ''}, about {pr['hours']:g} h.", "ok"))
            why: dict = {}
            for x in mk["missing"]:
                why.setdefault(x["why"], []).append(x["name"])
            for reason, names in why.items():
                listed = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
                how.append(_line(f"Your shop can't make {'the ' + listed if len(names) == 1 else listed}: {reason}.",
                                 "bad"))
            if mk["shop_default"]:
                how.append(_line("Planned for a jigsaw, a drill and a circular saw: say what's in your shop.", "info"))
        pats = [r for r in state.get("pattern_runs") or [] if r["part"] == pid]
        if any(x["kind"] == "sheet" for x in (mk or {}).get("pieces", [])):        # patterns are for flat pieces
            if pats and pats[0].get("version") == p["version"]:
                url = f"/api/designs/{state['slug']}/patterns/{pats[0]['id']}/"
                how.append(_line(f"Patterns ready: {pats[0]['pages']} pages to print full size, or project and trace.",
                                 "ok", action="patterns",
                                 links=[{"label": "Print full size", "url": url + "print-full-size.pdf"},
                                        {"label": "Measure and mark", "url": url + "measure-and-mark.pdf"},
                                        {"label": "Project", "url": url + "index.html"}]))
            else:
                how.append(_line("Make the patterns to print or project.", "info", action="patterns"))
    elif p.get("role") != "fixed":
        how.append(_line("Not known yet: it doesn't say what it's built from.", "warn"))
    return [_card("what", "What is it?", what),
            _card("work", "Will it work?", work, "Say what it must do and I'll check it."),
            _card("buy", "What do I buy?", buy),
            _card("make", "How do I make it?", how, "Say what it's built from and I'll plan the making.")]


def _and(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _cost(store: DesignStore, pid: str, report: dict) -> Optional[float]:
    from . import cutplan, scorecard

    try:
        report = {**report, "pieces_raw": C.takeoff(C._items(C.declared(store, pid)))}
        plans = cutplan.list_runs(store, pid)
        plan = plans[0] if plans and plans[0].get("version") == store.design.part(pid).version else None
        return scorecard.cost_and_waste(store, {pid: report}, {pid: plan})["usd"]
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# What it's held to (step 2): the conversation's checks, judged on what's already measured
# ---------------------------------------------------------------------------
def measured(store: DesignStore, state: dict) -> dict:
    """What the checks can be judged by without running anything: the strength checks on each part's current
    version, its weight and cost, what the shop can't make, and print time. ``{metric: value}``."""
    from . import making

    out: dict = {}
    current = {p["id"]: p["version"] for p in state["parts"]}
    safeties, breaks = [], []
    for pid in current:
        run = next((r for r in state.get("load_runs") or [] if r["part"] == pid), None)
        if run and run.get("version") == current[pid] and run.get("safety") is not None:
            safeties.append(run["safety"])
            breaks += [c["breaks_lb"] for c in run["cases"] if c.get("breaks_lb")]
    if safeties:
        out["strength.safety"] = min(safeties)
    if breaks:
        out["strength.breaks_lb"] = min(breaks)
    weight = usd = missing = hours = 0.0
    weighed = False
    for p in state["parts"]:
        if not p.get("built") or p.get("role") == "fixed":
            continue
        try:
            rep = C.report(store, p["id"])
        except Exception:  # noqa: BLE001
            continue
        weighed = True
        weight += rep["mass_lb"]
        usd += _cost(store, p["id"], rep) or 0.0
        try:
            mk = making.plan(store, p["id"])
            missing += len(mk["missing"])
            hours += sum(x["hours"] for x in mk["printed"])
        except Exception:  # noqa: BLE001
            pass
    if weighed:
        out.update({"weight.total_lb": round(weight, 1), "cost.usd": round(usd, 2), "make.not_in_shop": missing})
        if hours:
            out["print.hours"] = round(hours, 1)
    return out


def _num(metric: str, v: float, unit: str = "") -> str:
    from .goals import METRICS

    unit = METRICS.get(metric, ("", unit, ""))[1] or unit
    if unit == "$":
        return f"${v:,.0f}"
    if unit == "×":
        return f"{v:g}x" if v < 10 else "more than 10x"
    if v == 1 and unit.endswith("s") and unit not in ("lbs",):
        unit = unit[:-1]                                    # 1 sheet, 1 piece
    return f"{v:g} {unit}".strip()


def held_to(state: dict, now: dict) -> list[dict]:
    """One line per check the design is held to: a verdict (from what's measured now, else the last
    scorecard, said so if a part has changed since), or what it needs to be checked."""
    card = (state.get("scorecards") or [None])[0]
    scored = {k: m.get("value") for k, m in ((card or {}).get("metrics") or {}).items()
              if isinstance(m.get("value"), (int, float)) and not isinstance(m.get("value"), bool)}
    units = {k: m.get("unit", "") for k, m in ((card or {}).get("metrics") or {}).items()}
    stale = bool(card) and any(card.get("versions", {}).get(p["id"]) not in (None, p["version"])
                               for p in state["parts"])
    out = []
    for c in (state.get("goals") or {}).get("checks") or []:
        label = c.get("label") or c["id"]
        label = label[0].upper() + label[1:]
        if c.get("source") == "proposed":
            out.append(_line(f"Proposed: {label}. Keep or drop it under the numbers.", "info", goal=c["id"]))
            continue
        v, late = now.get(c["metric"]), False
        if v is None and c["metric"] in scored:
            v, late = scored[c["metric"]], stale
        assumed = " (assumed)" if c.get("source") == "assumed" else ""
        if v is None:
            how = ("Check it holds" if c["metric"].startswith("strength") else "Score it")
            out.append(_line(f"{label}{assumed}: not checked yet. {how}.", "warn",
                             study="load" if c["metric"].startswith("strength") else None))
            continue
        ok = v >= c["limit"] if c.get("op", ">=") == ">=" else v <= c["limit"]
        out.append(_line(f"{'✓' if ok else '✗'} {label}{assumed}: {_num(c['metric'], v, units.get(c['metric'], ''))}"
                         + (" (scored before the last change: score it again)." if late else "."),
                         "warn" if late else "ok" if ok else "bad",
                         study="load" if c["metric"].startswith("strength") else None))
    return out


# ---------------------------------------------------------------------------
# The whole design
# ---------------------------------------------------------------------------
def design(store: DesignStore, state: dict) -> list[dict]:
    parts = [p for p in state["parts"] if p.get("role") != "fixed"]
    # a design that's one part (the stool) answers with that part's own list and plan (CALI-59)
    solo = {c["key"]: c for c in part(store, state, parts[0]["id"])} if len(parts) == 1 else {}
    what = [_line(_sentence(state.get("prompt") or state["name"]))]
    if solo:
        what += solo["what"]["lines"][1:]
    elif parts:
        what.append(_line(f"{len(parts)} part{'s' if len(parts) != 1 else ''}: " + ", ".join(p["id"] for p in parts)))
    elif state.get("building"):
        what.append(_line("Building it now: these fill in as it goes.", "info"))
    else:
        what.append(_line("Not built yet: answer its questions and press Build it.", "warn"))
    assumed = sum(1 for r in state.get("requirements") or [] if r.get("source") == "assumed")
    if assumed:
        what.append(_line(f"{assumed} answer{'s' if assumed != 1 else ''} assumed: check them under the numbers.", "warn"))

    now = measured(store, state) if parts else {}
    work = held_to(state, now) if parts else []
    card = (state.get("scorecards") or [None])[0]
    if card and not work:
        s = card["summary"]
        fails = [c for c in card["checks"] if c["status"] == "fail"]
        stale = any(card.get("versions", {}).get(p["id"]) not in (None, p["version"]) for p in parts)
        work.append(_line(f"{s['pass']} check{'s' if s['pass'] != 1 else ''} pass" + (
            f", {s['fail']} fail: " + "; ".join((c.get("label") or c["id"]) for c in fails[:2]) if fails else ".")
            + (" (A part has changed since: score it again.)" if stale else ""),
            "bad" if fails else "warn" if stale else "ok"))
    elif not work:
        work.append(_line("Nothing to hold it to yet: say what it must do.", "warn"))

    buy = list(solo["buy"]["lines"]) if solo else []
    if now.get("cost.usd") and not solo:
        buy.append(_line(f"About ${now['cost.usd']:,.0f} for everything"
                         + (f" (${card['cost']['waste_usd']:,.0f} of it offcut, when last scored)."
                            if card and card.get("cost", {}).get("waste_usd") else ".")))
    if now.get("weight.total_lb") is not None and not solo:
        lb = now["weight.total_lb"]
        buy.append(_line(f"It all weighs {lb:g} lb" + (", easy for a kid to carry." if lb <= 10 else ".")))
    if not buy:
        buy.append(_line("Not known yet: no part says what it's built from.", "info"))

    make = [ln for ln in solo["make"]["lines"]] if solo else []
    rel = (state.get("releases") or [None])[0]
    if rel:
        url = f"/api/designs/{state['slug']}/releases/{rel['id']}/files/"
        make.append(_line(f"Build package {rel['id']}: {len(rel['steps'])} steps, "
                          + ("ready to cut." if rel["ready"] else "not ready: a check fails."),
                          "ok" if rel["ready"] else "bad", action="release",
                          links=[{"label": "Open the build book", "url": url + "index.html"}]
                          + ([{"label": "The kids' build book", "url": url + rel["kids"]}] if rel.get("kids") else [])))
    elif not solo:
        make.append(_line("No build package yet: make one when it's ready.", "info", action="release"))
    else:
        make.append(_line("Or make the whole build package: the build book, cut lists and drawings.", "info",
                          action="release"))
    return [_card("what", "What is it?", what), _card("work", "Will it work?", work),
            _card("buy", "What do I buy?", buy), _card("make", "How do I make it?", make)]


def answers(store: DesignStore, state: dict, part_id: Optional[str] = None) -> list[dict]:
    """The four cards for the design, or for one of its parts."""
    return part(store, state, part_id) if part_id else design(store, state)
