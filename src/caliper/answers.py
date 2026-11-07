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
from . import verdicts
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


def _carve_offer(store: DesignStore, state: dict, p: dict, mk: dict) -> Optional[dict]:
    """A printed part, on a design whose objective is its print time or its weight, with a carve to try (#89 item 6:
    165 h of printing "as fast as possible", and nothing offered the carve): one line that offers it. Not on a part
    already carved, nor one with nothing it must hold (a carve keeps what it holds)."""
    if not mk.get("printed") or not p.get("loads") or p.get("carved"):
        return None
    aims = [o.get("metric") or "" for o in (state.get("goals") or {}).get("objectives") or []]
    if not any(m.startswith(("print.", "weight.")) for m in aims):
        return None
    try:
        name = next((it.get("name") for it in C.declared(store, p["id"]).get("construction") or []
                     if isinstance(it, dict) and it.get("kind") == "printed"), None)
    except Exception:  # noqa: BLE001 — the offer is said with the part's own name
        name = None
    return _line(f"Carve the {name or p['id'].replace('_', ' ')} where it isn't working, to print less of it: try "
                 f"Carve it.", "info", action="carve")


def _strays(meta: dict, inches: bool) -> str:
    """What the mesh left out, its height in the design's units (#89, #137 P2 item 11: "at z 14.0–15.6 mm" on an inch
    design); measure's own words where it didn't say where."""
    n, z = meta.get("strays_n"), meta.get("strays_z")
    if not n or not z:
        return meta["strays"]
    lo, hi = _len(z[0], inches), _len(z[1], inches)
    return (f"left out {n} stray face{'s' if n != 1 else ''} from the CAD's meshing (at z {lo}"
            + (f"–{hi}" if hi != lo else "") + ")")


def _wall(mm: float, inches: bool = False) -> str:
    """A wall's thickness, or a voxel's size: in mm, whatever the design's units (#139 review: walls in mm everywhere,
    heights and positions in the design's), two places under 1 mm (0.25 mm, #137 item 2)."""
    return (f"{mm:.2f}".rstrip("0").rstrip(".") if mm < 1 else
            f"{mm:.1f}".removesuffix(".0") if mm < 10 else f"{mm:.0f}") + " mm"


def _small_len(mm: float, inches: bool) -> str:
    """A small length in inches to the nearest 1/32 (5/32 in), and in mm where that would round to nothing, never
    "0 in" (CALI-97, #100 item 5): what the chat says beside a number in mm."""
    from math import gcd

    if inches and mm >= IN:
        return _len(mm, True)
    n = round(mm / IN * 32)
    if inches and n >= 1:
        g = gcd(n, 32)
        return f"{n // g}/{32 // g} in"
    # under 1 mm, two places: a 0.25 mm wall is that, not "0.2" here and "0.3" on the page (#137 item 2)
    return (f"{mm:.2f}".rstrip("0").rstrip(".") if mm < 1 else
            f"{mm:.1f}".removesuffix(".0") if mm < 10 else f"{mm:.0f}") + " mm"


def _case_line(pid: str, run: dict, c: dict, filled: Optional[str], stale: bool, inches: bool) -> dict:
    """The part card's line for one load case: its words from its one verdict (CALI-112)."""
    from . import load_study as L

    older = " (Checked on an older version: check again.)" if stale else ""
    v = verdicts.case(run, c, filled=filled, stale=stale)   # an older run's ✓ is "older version" (#132 review)
    if v["kind"] == "untrusted":                     # ran on a block: no ✓ from it (CALI-96); this wins
        return _line(untrusted(pid, filled), "warn", study="load")   # the number: the panel, badged
    if v["kind"] in ("unresolved", "unchecked"):     # an FEA that can't see the wall is no ✓ (CALI-97)
        return _line(coarse(run, inches) + older, "warn", study="load")
    # a verdict on the printed model says so in a word, and why one click down by the promise (CALI-86)
    rough = L.rough(run, c)
    about = "about " if rough else ""
    if v["kind"] == "holds":
        text = f"Holds {c['name'].lower()}, {about}{_times(c['safety'])}."
    elif v["kind"] == "fails":
        text = f"Doesn't hold {c['name'].lower()}: only {about}{_times(c['safety'])}, and it needs {run['min_safety']:g}."
        if filled:                                   # a ✗ stays a ✗: the block failed, the part is weaker
            text += filled_fail(filled)
        else:                                        # where it fails first, and how sure (#137 item 2)
            where, thin_here = worst_at(run, c, inches)
            wall = _wall(c["fea"]["wall_mm"], inches) if where else ""
            if v.get("coarse") and thin_here:        # among walls the voxels can't see: the fail may be the model's
                text += (f" Its worst stress, in one run at {_wall(run['spacing_mm'])} voxels, is {where}, where its "
                         f"wall is {wall}, too thin for the voxels to see: the fail may be the model's. "
                         + ("Check it again finer." if run.get("finer") else
                            "A hand check or a printed test piece is the way to know."))
            elif where:                              # the voxels see the wall where it's worst
                text += f" Its worst stress is {where}."
                if v.get("coarse"):                  # the thin walls are said apart from it, not as its cause
                    text += (f" Separately, its thinnest walls, {_wall(run['thinnest_mm'])}{_thin_at(run, inches)}, "
                             f"are too thin for the voxels to see.")
            elif v.get("coarse"):                    # an older run: where isn't known (CALI-97's words)
                text += " " + coarse(run, inches, holds=False)
        pl = c.get("plate") or {}
        if pl.get("done") and c.get("governs") != "plate" and pl.get("safety_across") is not None:
            # a second opinion by hand on the panel it lands on (#137 item 7: the seat on its ring)
            how = (f", as a round plate held at its ring's outer edge ({_len(pl['ring_mm'], inches)} across)"
                   if pl.get("support") == "ring" else "")
            text += f" By hand, the {pl['piece']} on its own{how}: {_times(pl['safety_across'])}."
    else:                                            # any other kind: its word, never a ✓ (CALI-112)
        text = f"{c['name'][:1].upper() + c['name'][1:]}: {v['word']}, {about}{_times(c['safety'])}."
    return _line(text + older, v["status"], study="load",
                 **({"rough": L.ROUGH} if rough else {}))


def _rules_line(rules: list[dict]) -> dict:
    """A part's own rules in a line: "all pass" only when every rule ran and passed (#132 review); an error is a
    fail, and a rule that waits (deferred) is said, never counted."""
    bad = [r for r in rules if r["status"] in ("fail", "error")]
    waits = [r for r in rules if r["status"] not in ("pass", "fail", "error")]
    return _line(f"{len(bad)} of its rules fail: {', '.join(r['id'] for r in bad[:3])}." if bad else
                 f"{len(rules) - len(waits)} of its {len(rules)} rules pass; {len(waits)} not checked yet: "
                 f"{', '.join(r['id'] for r in waits[:3])}." if waits else
                 f"Its {len(rules)} rule{'s' if len(rules) != 1 else ''} all pass.",
                 "bad" if bad else "warn" if waits else "ok")


def _why_not(rel: dict) -> str:
    """Why a build package isn't ready, in its own words (CALI-96: not trusted; CALI-110: not resolved)."""
    return verdicts.summary((rel.get("card") or {}).get("summary"))["why"] or "a check isn't settled"


def _thin_at(run: dict, inches: bool) -> str:
    """Where a run's thinnest wall is, as it recorded it (#136): " around z 16.1 in", " in the seat top", or ""."""
    w = run.get("thinnest_where") or {}
    return (f" in the {w['piece']}" if w.get("piece") else
            f" around z {_len(w['at'][2], inches)}" if w.get("at") else "")


def worst_at(run: dict, c: dict, inches: bool) -> tuple[str, Optional[bool]]:
    """Where a case's worst stress is in its run ("in the cone around z 15.3 in"), and whether the wall there is too
    thin for its voxels (None where the run didn't record it: older runs, whose ``in`` named the nearest wood even for
    a printed part, #137 item 2)."""
    from . import load_study as L

    fea = c.get("fea") or {}
    if "wall_mm" not in fea or not fea.get("at"):
        return "", None
    where = (f"in the {fea['in']} " if fea.get("in") else "") + f"around z {_len(fea['at'][2], inches)}"
    s = run.get("spacing_mm")
    return where, (not L._sees(fea["wall_mm"] / s)) if s else None


def coarse(run: dict, inches: bool = True, holds: bool = True) -> str:
    """What a verdict says when the FEA that governs it couldn't see the wall it's checking (CALI-97). A ✓ is no
    verdict then: not resolved yet (a finer run can see it) or not checked (none a study may make can). A ✗ stays a
    ✗, and says the fail may be the model's."""
    from . import load_study as L

    walls = f"thinnest walls, {_wall(run.get('thinnest_mm') or 0)}{_thin_at(run, inches)}"   # which, and where (#139)
    if not holds:
        return (f"The fail may be the model's: the voxels can't see its {walls}. "
                + ("Check it again finer." if run.get("finer") else
                   "A hand check or a printed test piece is the way to know."))
    if run.get("finer"):
        return f"Not resolved yet: the check was too coarse to see its {walls}. Check it again finer."
    return L.NOT_CHECKED
def filled_fail(why: Optional[str]) -> str:
    """What a ✗ adds when its check didn't run on the part as built (#89, #100's merge checks): on a filled-in shape,
    the part as built is *likely* weaker (taking material away can, rarely, lower a peak); where its shape couldn't
    be checked against its pieces, that is said, not "a filled-in shape", which isn't known."""
    if (why or "").startswith(("couldn't", "Not trusted yet: I couldn't")):     # filled()'s, or untrusted()'s
        return " Its shape couldn't be checked against its pieces, so this number may not be the part's."
    return " It ran on a filled-in shape, so the part as built is likely weaker."


def untrusted(pid: str, why: str = "") -> str:
    """What a strength verdict on a filled-in solid says instead of holding (CALI-96), or one whose shape couldn't
    be checked against its pieces at all (which fails closed: never holding)."""
    if why.startswith("couldn't"):
        return f"Not trusted yet: I {why}, so I can't say the strength check ran on the part as built. Check it again."
    return (f"Not trusted yet: the strength check ran on a filled-in shape, not the {pid.replace('_', ' ')} as built. "
            f"Fix its shape first (say \"fix its shape to match its pieces\").")


def rests_on_model(metric: str) -> bool:
    """Whether a scorecard check's number comes from a strength or frame model (and so carries the promise): not a
    weight, a cost, or whether the pieces fit a sheet (CALI-86)."""
    m = metric or ""
    return m.startswith(("strength.", "frame.")) or m.endswith("safety") or "yield" in m


def _card(key: str, q: str, lines: list[dict], hint: str = "") -> dict:
    card = {"key": key, "q": q, "status": _worst(lines) if lines else "info", "lines": lines, "hint": hint}
    # any verdict resting on a model (a strength or frame study, or the scorecard's checks) says what it promises
    if any((ln.get("study") in ("load", "frame") or ln.get("model")) and ln["status"] in ("ok", "bad") for ln in lines):
        card["promise"] = PROMISE + "".join(f" {r}" for r in dict.fromkeys(ln["rough"] for ln in lines if ln.get("rough")))
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

            geom = store.part_geometry(pid)                  # cached by the assembly (path, mtime)
            off = sorted((r for r in consistency.check(C.declared(store, pid), geom)
                          if r.status == "fail" and r.detail), key=lambda r: r.id != "construction_volume")
            meta = geom.require_mesh().metadata
            strays = _strays(meta, inches) if meta.get("strays") else None
        except Exception:  # noqa: BLE001 — the card says what it can
            off, strays = [], None
        if strays:                                   # what the mesh left out, said once (CALI-118)
            what.append(_line(f"I {strays}: it enclosed nothing and weighs nothing.", "info"))
        if off:
            what.append(_line(f"Its 3D shape and its pieces don't match: {off[0].detail}. Say \"fix its shape to "
                              f"match its pieces\" and I'll revise it.", "bad"))

    # Will it work?
    work = []
    if p.get("role") == "fixed":
        work.append(_line("It's a reference (like the car): nothing to check."))
    work += _broken(p)                                     # a rule of its own it breaks, first (#137 item 1)
    runs = [r for r in state.get("load_runs") or [] if r["part"] == pid]
    if runs:
        run, stale = runs[0], runs[0].get("version") != p["version"]
        from . import consistency
        from . import load_study as L

        filled = consistency.filled(store, pid)              # the check ran on a block, not the part (CALI-96)
        for c in run["cases"]:
            if c.get("safety") is not None:
                work.append(_case_line(pid, run, c, filled, stale, inches))
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
            if tried["status"] in ("bad", "warn"):
                # a test that went against the prediction outranks it: no ✓ left above a failed test (CALI-86)
                work = [ln for ln in work if not (ln.get("study") == "load" and ln["status"] == "ok")]
            work.append(_line(tried["text"], tried["status"], study="trial"))
    frames = [r for r in state.get("frame_runs") or [] if r["part"] == pid]
    if frames:
        d = frames[0].get("drawn") or {}
        if d.get("safety") is not None:
            # an older frame run (or one from before it recorded its version) isn't the frame as it is (#132 review)
            v = verdicts.meets(d["safety"], frames[0].get("min_safety"),
                               stale=frames[0].get("version") != p["version"])
            work.append(_line(f"The frame holds, {_times(d['safety'])}." if v["kind"] == "holds" else
                              f"The frame read {_times(d['safety'])} on an older version: check it again." if v["kind"] == "stale" else
                              f"The frame is too weak as drawn: {_times(d['safety'])}, it needs "
                              f"{frames[0].get('min_safety')}.", v["status"], study="frame"))
    mine = {r["id"] for r in p.get("rules") or []}
    rules = [r for r in (state.get("report") or {}).get("results", []) if r.get("id") in mine]
    if len([x for x in state["parts"] if x.get("role") != "fixed"]) == 1 and p.get("role") != "fixed":
        # the only part: what the design is held to is what it's held to (the strength lines say it already)
        work += [ln for ln in held_to(state, measured(store, state)) if ln.get("study") != "load"]
    if rules:
        work.append(_rules_line(rules))

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
        if lb is None:                                   # unknown, never the rest's weight (#125 review)
            buy.append(_line(f"Its weight isn't known: {report.get('unweighed') or C.UNWEIGHED}.", "warn"))
        else:
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
            offer = _carve_offer(store, state, p, mk)
            if offer:
                how.append(offer)
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
    from . import load_study as L

    latest = [next((r for r in state.get("load_runs") or [] if r["part"] == pid), None) for pid in current]
    cases = [(r, c) for r in latest if r and r.get("version") == current.get(r["part"])
             for c in r.get("cases") or [] if c.get("safety") is not None]
    inches = (state.get("display_units") or "in") == "in"
    said = [(r, verdicts.case(r, c)) for r, c in cases]
    held = [r for r, v in said if v["kind"] in ("unresolved", "unchecked")]
    if held:                                           # a ✓ can't rest on an FEA that can't see the wall (CALI-97)
        out["strength.unresolved"] = coarse(held[0], inches)
    failed = [r for r, v in said if v["kind"] == "fails" and v.get("coarse")]
    if failed:                                         # ...and a ✗ on one says the fail may be the model's
        out["strength.coarse_fail"] = coarse(failed[0], inches, holds=False)
    if any(L.rough(r, c) for r, c in cases):
        out["strength.rough"] = True                   # the printed model's number: "about", as the part card says
    from . import consistency

    # a design's strength never leaves a part out (#132 review): a part with loads() and no check of this version is
    # unchecked, or older; its number isn't in the min above, so the rest can't read as holding for it
    loaded = [p for p in state["parts"] if p.get("loads") and p.get("role") != "fixed"]
    runs = {pid: next((r for r in state.get("load_runs") or [] if r["part"] == pid), None) for pid in current}
    unchecked = [p["id"] for p in loaded if runs.get(p["id"]) is None or runs[p["id"]].get("safety") is None]
    older = [p["id"] for p in loaded if p["id"] not in unchecked and runs[p["id"]].get("version") != p["version"]]
    if unchecked:
        out["strength.unchecked"] = ("not checked yet on the " + " and the ".join(x.replace("_", " ") for x in unchecked)
                                     + ": Check it holds")
    if older:
        out["strength.stale"] = ("the " + " and the ".join(x.replace("_", " ") for x in older)
                                 + " changed since its strength check: check it again")
    filled = [pid for pid in current if any(r["part"] == pid and r.get("version") == current[pid]
                                            for r in state.get("load_runs") or []) and consistency.filled(store, pid)]
    if filled:                                         # a verdict measured on a filled-in solid isn't one (CALI-96)
        out["strength.filled"] = untrusted(filled[0], consistency.filled(store, filled[0]) or "")
    if safeties:
        out["strength.safety"] = min(safeties)
    if breaks:
        out["strength.breaks_lb"] = min(breaks)
    from . import trials

    tested = [t for t in (trials.summary(store, pid) for pid in current) if t and t["status"] in ("bad", "warn")]
    if tested:                                         # the worst real test, which outranks the prediction (CALI-86)
        out["strength.test"] = min(tested, key=lambda t: ORDER.index(t["status"]))
    weight = usd = missing = hours = 0.0
    weighed, unweighed = False, None
    for p in state["parts"]:
        if not p.get("built") or p.get("role") == "fixed":
            continue
        try:
            rep = C.report(store, p["id"])
        except Exception as e:  # noqa: BLE001 — a part that can't be weighed is unknown, never left out (#132)
            weighed, unweighed = True, unweighed or f"not checked: the {p['id'].replace('_', ' ')} couldn't be weighed ({e})"
            continue
        weighed = True
        if rep.get("mass_lb") is None:             # one part unknown: the total is too, never the rest's (#125)
            unweighed = unweighed or rep.get("unweighed") or C.UNWEIGHED
        else:
            weight += rep["mass_lb"]
        usd += _cost(store, p["id"], rep) or 0.0
        try:
            mk = making.plan(store, p["id"])
            missing += len(mk["missing"])
            hours += sum(x["hours"] for x in mk["printed"])
        except Exception:  # noqa: BLE001
            pass
    if weighed:
        out.update({"weight.total_lb": None if unweighed else round(weight, 1), "cost.usd": round(usd, 2),
                    "make.not_in_shop": missing})
        if unweighed:
            out["weight.unweighed"] = unweighed
        if hours:
            out["print.hours"] = round(hours, 1)
    return out


def _against(c: dict, failed: bool, unit: str = "") -> str:
    """A goal's own limit beside its number (#137 item 5: "13.1 lb" never said it was over a 10 lb cap)."""
    lim = c.get("limit")
    if not isinstance(lim, (int, float)) or isinstance(lim, bool) or c["metric"].startswith("strength"):
        return ""                                  # a strength goal's label says what it needs ("2 times over")
    cap, said = c.get("op", ">=") in ("<=", "<"), _num(c["metric"], float(lim), unit)
    if cap:
        return f", over its {said} cap" if failed else f", within its {said} cap"
    return f", short of the {said} it needs" if failed else f", against the {said} it needs"


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
    stale = bool(card) and (bool(card.get("outdated")) or any(
        card.get("versions", {}).get(p["id"]) not in (None, p["version"]) for p in state["parts"]))
    out = []
    for c in (state.get("goals") or {}).get("checks") or []:
        label = c.get("label") or c["id"]
        label = label[0].upper() + label[1:]
        if c.get("source") == "proposed":
            out.append(_line(f"Proposed: {label}. Keep or drop it under the numbers.", "info", goal=c["id"]))
            continue
        test = now.get("strength.test") if c["metric"].startswith("strength") else None
        if test:                                       # what a real test did, over what the check predicted
            out.append(_line(f"{'✗' if test['status'] == 'bad' else '!'} {label}: {test['text']}", test["status"],
                             study="load", model="scorecard"))
            continue
        assumed = " (assumed)" if c.get("source") == "assumed" else ""
        unknown = now.get("weight.unweighed") if c["metric"].startswith("weight") else None
        if unknown:            # unknown now: never the last card's lower total (#125, #132): one verdict, said
            verdict = verdicts.goal(None, incomplete=unknown)
            out.append(_line(f"{label}{assumed}: {verdict.get('why') or unknown}.", "warn"))
            continue
        v, late = now.get(c["metric"]), False
        if v is None and c["metric"] in scored:
            v, late = scored[c["metric"]], stale
        if v is None:
            how = ("Check it holds" if c["metric"].startswith("strength") else "Score it")
            out.append(_line(f"{label}{assumed}: not checked yet. {how}.", "warn",
                             study="load" if c["metric"].startswith("strength") else None))
            continue
        met = verdicts.compare(v, c.get("op", ">="), c["limit"])
        strength = c["metric"].startswith("strength")
        untrue = now.get("strength.filled") if strength else None
        # one verdict (CALI-112): a ✗ stays a ✗, then not trusted (CALI-96), then not resolved (CALI-97)
        older = now.get("strength.stale") if strength else None
        verdict = verdicts.goal(met, untrusted=untrue, unresolved=now.get("strength.unresolved") if strength else None,
                                stale=late or bool(older),
                                incomplete=now.get("strength.unchecked") if strength else None)
        if verdict["kind"] == "untrusted":             # the verdict first; which check it is follows (#96 item 5)
            out.append(_line(f"{untrue} ({label[:1].lower() + label[1:]}{', assumed' if c.get('source') == 'assumed' else ''})", "warn",
                             study="load", model=rests_on_model(c["metric"])))
            continue
        if verdict["kind"] == "unresolved":            # no ✓ on an FEA that can't see the wall (CALI-97)
            out.append(_line(f"! {label}{assumed}: {now['strength.unresolved']}", "warn",
                             study="load", model=rests_on_model(c["metric"])))
            continue
        num = _num(c['metric'], v, units.get(c['metric'], ''))
        if strength and now.get("strength.rough"):
            num = "about " + num                       # the printed model's number, as the part card says (CALI-97)
        failed = verdict["kind"] == "fails"
        why = (filled_fail(untrue) if failed and untrue   # still ✗
               else f" {now['strength.coarse_fail']}" if failed and strength and now.get("strength.coarse_fail") else "")
        if verdict["kind"] == "waiting":               # a part left out isn't covered by the rest (#132 review)
            out.append(_line(f"! {label}{assumed}: {num} for the rest, but {verdict['why']}.", "warn",
                             study="load" if strength else None, model=rests_on_model(c["metric"])))
            continue
        # never a ✓ for an older check or score (#132 review): it says when, and what to do
        later = (" (scored before the last change: score it again)." if late
                 else f" ({older})." if verdict["kind"] == "stale" and older else "." + why)
        out.append(_line(f"{'✗' if failed else '✓' if verdict['kind'] == 'holds' else '!'} {label}{assumed}: {num}"
                         + _against(c, failed, units.get(c['metric'], '')) + later,
                         "warn" if late else verdict["status"],
                         study="load" if c["metric"].startswith("strength") else None,
                         model=rests_on_model(c["metric"])))
    return out


# ---------------------------------------------------------------------------
# The whole design
# ---------------------------------------------------------------------------
def _broken(p: dict, named: bool = False) -> list[dict]:
    """A part's own rules it breaks as built now, each a line from its verdict (#137 item 1: the bar stool's locked
    shell wall, broken, and no card said so)."""
    from . import part_rules

    who = f"The {p['id'].replace('_', ' ')} breaks" if named else "Breaks"
    return [_line(f"✗ {who} its rule {r['said']}.", r["verdict"]["status"], study="rule")
            for r in part_rules.failing(p.get("rules") or [])]


def design(store: DesignStore, state: dict) -> list[dict]:
    parts = [p for p in state["parts"] if p.get("role") != "fixed"]
    # a design that's one part (the stool) answers with that part's own list and plan (CALI-59)
    solo = {c["key"]: c for c in part(store, state, parts[0]["id"])} if len(parts) == 1 else {}
    what = [_line(_sentence(state.get("prompt") or state["name"]))]
    if solo:
        # the part's own description, as What do I buy? already reads it (#89 item 3: the raw "I want to make…")
        what = list(solo["what"]["lines"][:1]) + solo["what"]["lines"][1:]
    elif parts:
        what.append(_line(f"{len(parts)} part{'s' if len(parts) != 1 else ''}: " + ", ".join(p["id"] for p in parts)))
    elif state.get("building"):
        what.append(_line("Building it now: these fill in as it goes.", "info"))
    elif state.get("plan"):                   # planned, not built: the person reviews it first (CALI-35, #3a)
        pl = state["plan"]
        what.append(_line(pl["headline"], "warn"))
        # with no key the page shows the key's note where Build it would be: the line says so, never "press" (#89)
        what.append(_line("That's the plan, before anything's drawn: its numbers and the checks between the parts are "
                          "under the numbers. " + ("Say what to change, or press Build it." if state.get("claude", True)
                                                   else "Building it needs Claude, which isn't set up here."), "info"))
    else:
        what.append(_line("Not built yet: answer its questions and press Build it.", "warn"))
    assumed = sum(1 for r in state.get("requirements") or [] if r.get("source") == "assumed")
    if assumed:
        what.append(_line(f"{assumed} answer{'s' if assumed != 1 else ''} assumed: check them under the numbers.", "warn"))

    now = measured(store, state) if parts else {}
    # a part's own rule it breaks leads the design's answer too (#137 item 1)
    broken = [ln for p in parts for ln in _broken(p, named=len(parts) > 1)]
    work = held_to(state, now) if parts else []
    card = (state.get("scorecards") or [None])[0]
    if card and not work:
        s = card["summary"]
        fails = [c for c in card["checks"] if c["status"] == "fail"]
        stale = bool(card.get("outdated")) or any(card.get("versions", {}).get(p["id"]) not in (None, p["version"])
                                                  for p in parts)
        # never a pass: a check that couldn't run (#103 review), nor one measured on a filled-in shape (CALI-96)
        untrusted, unresolved = s.get("untrusted") or 0, s.get("unresolved") or 0     # never a pass (CALI-110)
        waits = (s.get("unknown") or 0) - untrusted - unresolved
        said = (f"{s['pass']} check{'s' if s['pass'] != 1 else ''} pass" if s["pass"] or fails
                else "No check has run yet" if waits and not untrusted and not unresolved else "No check passes yet")
        rest = ([f"{untrusted} not trusted"] * bool(untrusted) + [f"{unresolved} not resolved"] * bool(unresolved)
                + [f"{waits} not checked yet"] * bool(waits))
        work.append(_line(said + (
            f", {s['fail']} fail: " + "; ".join((c.get("label") or c["id"]) for c in fails[:2]) if fails else "")
            + (f"{',' if s['pass'] or fails else ':'} " + ", ".join(rest) if rest else "") + "."
            + (" (A part has changed since: score it again.)" if stale else ""),
            "bad" if fails else "warn" if stale or rest or not verdicts.summary(s)["counts_as_pass"] else "ok"))
    elif not work and not broken:
        work.append(_line("Nothing to hold it to yet: say what it must do.", "warn"))
    work = broken + work

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
        v = verdicts.release(rel, {p["id"]: p["version"] for p in state["parts"]})    # one verdict (#132 review)
        make.append(_line(f"Build package {rel['id']}: {len(rel['steps'])} steps, "
                          + ("ready to cut." if v["kind"] == "holds" else
                             "ready to cut as it was, but a part has changed since: make it again." if v["kind"] == "stale"
                             else f"not ready: {_why_not(rel)}."),
                          v["status"], action="release",
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
