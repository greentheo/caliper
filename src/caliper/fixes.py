"""CALI-189 (#300), slice A — "Things to fix" under *Will it work?*: what's measured wrong with a part, each with a tick,
the fix proposed, what kind of change it is and what it costs; then the **Known limits** apart, with no tick.

Theo, reading step-stool-5 v6's *Will it work?*: "maybe what would help is something like a 'items you can do to fix the
problems', give me some check boxes and if I check and submit them, it will go over to the builder and make those build
changes and rebuild".

Every row comes from what's measured: the part's own rules, its newest strength check (a piece of no declared size, a
case too coarse to see its walls, a panel or a wall that fails, a front edge nobody stands on, a check of an older
version) and the after-build findings that name it (#238 slice A). No model call makes the list. A fix is one of:

- ``number``: a parameter to set, through the Parameters route (#267): no designer;
- ``check``: the check again, finer or of this version: no designer;
- ``designer``: a change only the designer can make, said in a sentence for it.

What Caliper can't fix by itself (a joint nothing checks yet, a printed part's rough model, a verdict the FEA alone
gives between its holds) is a **known limit**: said, never ticked, never mixed in with the rows. Slice B adds
*Fix these*.
"""

from __future__ import annotations

import math
from typing import Optional

from .design import DesignStore

NUMBER, DESIGNER, CHECK, LOADS = "number", "designer", "check", "loads"
#: What each kind of change costs, before any time is known.
NUMBER_COST = "a number change, at once"
#: A change to the part's edited loads (#312): no designer, no rebuild; its checks are then of the loads before.
LOADS_COST = "a change to its loads, at once"


def _designer_cost(name: str) -> str:
    return f"a designer edit on the {name} (one Claude call)"


def _check_cost(minutes: Optional[float], finer: bool = False) -> str:
    from .better import _minutes

    what = "a finer check" if finer else "a check"
    return f"{what}, about {_minutes(minutes)}" if minutes else what


def _choice(fix: str, kind: str, cost: str, **more) -> dict:
    return {"fix": fix, "kind": kind, "cost": cost, **more}


def _row(rid: str, problem: str, choices: list[dict], part: str) -> dict:
    return {"id": rid, "problem": problem, "choices": choices, "part": part, "measured": True}


def _spoke(row: dict, cases, what: str) -> dict:
    """A check-made row with the cases it speaks for and what it's of, in words (#322 review): Fix these calls it fixed
    only where those cases pass in a fresh check, or no new row speaks for any of them."""
    return {**row, "cases": list(dict.fromkeys(cases)), "what": what}


def _removed(store: DesignStore, pid: str, names: list[str], these: str, name: str) -> dict:
    """Remove them (#324): a number change where one number turns every one of them off, built to be sure (step_stool's
    ``fillet_r``: 0 skips its strips; a ``fillet_gap`` that only shares the name doesn't), else the designer's. Only what
    a piece's Delete… has built for this version (#332 review: Things to fix never waits on a build): not built yet is the
    designer's."""
    from . import pieces

    try:
        found = [(pieces.known(store, pid, n) or (None, None))[0] for n in names] if store.is_scripted(pid) else [None]
    except (ValueError, OSError):                # no numbers to set, no script to read
        found = [None]
    sw = found[0] if found and all(f is not None and f == found[0] for f in found) else None
    if sw is None:
        return _choice(f"Remove the {these}", DESIGNER, _designer_cost(name))
    return _choice(f"Remove the {these}: {sw['param']} to 0", NUMBER, NUMBER_COST, param=sw["param"], value=0,
                   unit=sw["unit"])


def _these(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def _stock() -> list[float]:
    """The sheets a fix may name: the plate check's own stock table, to 1 in (#318 review: the buckling fix named
    1 1/2 in plywood from a list the plate check never offers)."""
    from .construction import THICKNESSES

    return [t for t in THICKNESSES if t <= 26]


def _thicker(t: float, safety: float, need: float, power: float) -> Optional[float]:
    """The thinnest stock sheet, thicker than ``t``, whose safety clears ``need`` where safety goes as thickness to
    ``power`` (a wall's buckling load, as t³). None when no stock sheet does."""
    want = t * (need / safety) ** (1.0 / power) if safety > 0 else math.inf
    return next((x for x in _stock() if x > t + 0.01 and x >= want - 1e-6), None)


def _x(safety: float, need: Optional[float]) -> str:
    """A safety as the card says it (``answers.safety_num``): cut toward safe, never up to what it needs (#318 review:
    1.96 read 2.0), and "under 0.1" for a tiny one, never "0×"."""
    from .answers import safety_num

    return f"{safety_num(safety, need)}×"


_COUNT = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def _part_name(p: dict) -> str:
    from .answers import part_name

    n = part_name(p)
    return n[:1].lower() + n[1:]                 # mid-sentence: "a designer edit on the step stool"


def _run_rows(store: DesignStore, p: dict, run: dict, name: str) -> tuple[list[dict], list[str]]:
    """The rows and known limits from the part's newest strength check."""
    from . import better, consistency, verdicts
    from . import load_study as L
    from .answers import joint_said
    from .materials import nominal

    pid = p["id"]
    rows, limits = [], []
    need = run.get("min_safety") or L.MIN_SAFETY
    stale = run.get("version") != p["version"]
    if stale:                                   # its numbers are of another version: none of them is this part's
        rows.append(_row("stale", f"Its strength check is of v{run.get('version')}, not this version",
                         [_choice("Check it again", CHECK, _check_cost((run.get("seconds") or 0) / 60))], pid))
        return rows, limits
    filled = consistency.filled(store, pid)
    edge = consistency.bare_edge(store, pid)
    cases = [c for c in run.get("cases") or [] if c.get("safety") is not None]
    said = [(c, verdicts.case(run, c, filled=filled, edge=bool(edge))) for c in cases]
    if run.get("unsized"):                      # a printed piece of no declared size (#272): its own row, its choice
        names = list(run["unsized"])
        these = _these(names)
        many = len(names) > 1 or names[0].rstrip().endswith("s")        # "fillet strips": one name, many (as the card)
        rows.append(_row("unsized", f"The {these} {'aren' if many else 'isn'}'t checked: "
                                    f"{'their' if many else 'its'} size isn't declared",
                         [_choice(f"They're trim, not holding anything up: declare the {these} trim", DESIGNER,
                                  _designer_cost(name)),
                          _choice(f"Give the {these} {'their' if many else 'its'} size: a declared section, in mm",
                                  DESIGNER, _designer_cost(name)),
                          _removed(store, pid, names, these, name)], pid))
    thin, spacing = run.get("thinnest_mm"), run.get("spacing_mm")
    coarse = bool(thin and spacing) and not L._sees(run.get("across") or thin / spacing)
    unresolved = [c["name"] for c, v in said if v["kind"] in ("unresolved", "unchecked")]
    if coarse and unresolved:                   # too coarse to see a wall: finer, where a finer check can see it
        finer = run.get("finer") or {}
        if finer.get("spacing_mm"):
            rows.append(_row("finer", f"{_these(unresolved)[:1].upper()}{_these(unresolved)[1:]}: not resolved, the "
                                      f"check was too coarse to see its thinnest wall",
                             [_choice(f"Check it again at {finer['spacing_mm']:g} mm", CHECK,
                                      _check_cost(finer.get("minutes"), finer=True), spacing_mm=finer["spacing_mm"])], pid))
        else:
            limits.append(L.NOT_CHECKED)
    if filled:                                  # checked on a solid with more in it than its pieces (CALI-96)
        rows.append(_row("filled", f"Its check ran on a solid with more in it than its pieces: {filled}",
                         [_choice("Make its shape match its pieces", DESIGNER, _designer_cost(name))], pid))
    if edge:                                    # where people stand wasn't loaded (CALI-94)
        rows.append(_row("edge", edge[:1].upper() + edge[1:],
                         [_choice("Add a case standing at its free edge", DESIGNER, _designer_cost(name))], pid))
    sheet = (run.get("sheet") or {}).get("pieces") or {}
    from . import construction as C

    panels_all = {it.get("name") for it in C.declared(store, pid).get("construction") or []   # every sheet, numbered or not
                  if isinstance(it, dict) and it.get("kind") == "sheet"}
    pending = _pending(store, pid)               # a case checked at one side of an open question, and which (#312)

    def note(names) -> str:
        said = [pending[n] for n in names if n in pending]
        return f"; {said[0]}" if said else ""

    def thicker(piece: str, t_mm: float, label: str, now: str) -> list[dict]:
        """A thicker sheet: a number where the run names its PARAMS entry, saying every piece it moves, with this piece
        alone as the designer's choice beside it (#318 review: ``ply_t`` sets all six panels); else the designer's."""
        param = sheet.get(piece)
        if not param:
            return [_choice(f"Make the {piece} from {label} instead of {now}", DESIGNER, _designer_cost(name))]
        moved = [k for k, v in sheet.items() if v == param]
        if len(moved) == 1:
            return [_choice(f"Make the {piece} from {label} instead of {now}", NUMBER, NUMBER_COST, param=param,
                            value=t_mm, unit="mm", moves=moved)]
        others = len(moved) - 1
        what = "every panel" if set(moved) >= panels_all else f"the {_these(moved)}"
        return [_choice(f"Make {what} {label} ({param} sets the {piece} and the other "
                        f"{_COUNT[others] if others < len(_COUNT) else others})", NUMBER,
                        f"a number change, at once: it moves the {_these(moved)}", param=param, value=t_mm, unit="mm",
                        moves=moved),
                _choice(f"Make the {piece} alone from {label}", DESIGNER, _designer_cost(name))]

    def otherwise(piece: str) -> list[dict]:
        """What's left where no stock sheet clears it: the designer's, each said."""
        return [_choice(f"Hold the {piece} up underneath: another support or a rail under it", DESIGNER, _designer_cost(name)),
                _choice(f"Brace the {piece}", DESIGNER, _designer_cost(name)),
                _choice("Ask it to hold less: a lighter load in its loads()", DESIGNER, _designer_cost(name))]

    failing = [(c, v) for c, v in said if v["kind"] == "fails"]
    covered: set = set()                        # the failing cases a row speaks for: every one gets a row (#318 review)
    for pick in better._sheet_picks(run, fails=True):     # a panel the plate check fails: the thinnest that holds
        on = [c for c, _ in failing if (c.get("plate") or {}).get("piece") == pick["piece"]]
        covered |= {c["name"] for c in on}
        rows.append(_spoke(_row(f"plate:{pick['piece']}", f"The {pick['piece']} fails by the plate check: "
                                                         f"{_x(pick['now_safety'], need)} where it needs {need:g}×"
                                                         + note(c["name"] for c in on),
                                thicker(pick["piece"], pick["t_mm"], pick["label"], pick["label_now"]), pid),
                           [c["name"] for c in on], f"the {pick['piece']}"))
    panels: dict = {}
    for c, _ in failing:                        # a panel the plate check fails that no stock sheet clears
        pl = c.get("plate") or {}
        if c["name"] not in covered and c.get("governs") == "plate" and pl.get("done") and pl.get("piece"):
            panels.setdefault(pl["piece"], []).append(c)
    for piece, on in panels.items():
        covered |= {c["name"] for c in on}
        tables = [{round(b["thickness_mm"], 2): b for b in c["plate"].get("by_thickness") or []
                   if b.get("safety_across") is not None} for c in on]
        common = sorted(set.intersection(*(set(t) for t in tables))) if tables else []
        thickest = (f": the thickest, {tables[0][common[-1]]['label']}, is "
                    f"{_x(min(tb[common[-1]]['safety_across'] for tb in tables), need)}") if common else ""
        rows.append(_spoke(_row(f"plate:{piece}", f"The {piece} fails by the plate check: "
                                                  f"{_x(min(c['safety'] for c in on), need)} "
                                                  f"where it needs {need:g}×; no stock sheet clears it{thickest}"
                                                  + note(c["name"] for c in on), otherwise(piece), pid),
                           [c["name"] for c in on], f"the {piece}"))
    for c, v in failing:
        if c["name"] in covered or c.get("governs") != "buckling":
            continue
        rowsb = [b for b in c.get("buckling") or [] if b.get("done") and b.get("safety") is not None]
        if not rowsb:
            continue
        covered.add(c["name"])
        b = min(rowsb, key=lambda r: r["safety"])
        if b.get("down") is False:              # pushed in the wall's own plane: the card says racking isn't checked
            from .answers import RACKING

            limits.append(RACKING)
        rid = f"buckling:{b['piece']}"
        if any(r["id"] == rid for r in rows):
            continue
        t = _thicker(b["thickness_mm"], b["safety"], need, 3.0)       # its buckling load goes as t³
        problem = f"The {b['piece']} buckles under {c['name']}: {_x(b['safety'], need)} where it needs {need:g}×"
        if t is not None:
            choices = thicker(b["piece"], t, nominal(t), nominal(b["thickness_mm"]))
            choices.append(_choice(f"Brace the {b['piece']}", DESIGNER, _designer_cost(name)))
        else:
            top = _stock()[-1]
            problem += (f"; no stock sheet clears it: the thickest, {nominal(top)}, is "
                        f"{_x(b['safety'] * (top / b['thickness_mm']) ** 3, need)}")
            choices = [_choice(f"Brace the {b['piece']}", DESIGNER, _designer_cost(name)),
                       _choice("Ask it to hold less: a lighter load in its loads()", DESIGNER, _designer_cost(name))]
        rows.append(_spoke(_row(rid, problem + note([c["name"]]), choices, pid), [c["name"]], f"the {b['piece']}"))
    for c, v in said:                           # a joint that gives first (#301): its own row, its fix by how it gives
        J = c.get("joints") or {}
        for jr in J.get("rows") or []:
            if jr.get("safety") is None or verdicts.meets(jr["safety"], need)["counts_as_pass"]:   # verdicts' own
                continue
            if v["kind"] == "fails" and c.get("governs") == "joint":
                covered.add(c["name"])
            rid = f"joint:{'|'.join(jr['pieces'])}"
            had = next((r for r in rows if r["id"] == rid), None)
            if had is not None:                  # one row a joint: each case it gives in, spoken for
                had["cases"] = list(dict.fromkeys((had.get("cases") or []) + [c["name"]]))
                if _more(jr) > _more(had["_jr"]):   # the count every case it speaks for passes at (#344)
                    had["choices"], had["_jr"] = _joint_choices(jr, name), jr
                continue
            first = (J.get("governing") or {}).get("pieces") == jr["pieces"]
            # "gives first" only where a joint governs the case; where a panel or the FEA does, the weakest joint (#318)
            verb = ("gives first under" if first and c.get("governs") == "joint" else
                    "is the weakest joint under" if first else "gives too under")
            rows.append(_spoke(_row(rid, f"The joint between {jr['between']} {verb} "
                                         f"{c['name']}: {jr['said']}; "
                                         f"{_x(jr['safety'], need)} where it needs {need:g}×" + note([c["name"]]),
                                    _joint_choices(jr, name), pid), [c["name"]], f"the joint between {jr['between']}")
                        | {"_jr": jr})
        if any(jr.get("said") == _racking() for jr in J.get("rows") or []):
            from .answers import RACKING

            limits.append(RACKING)
    for r in rows:
        r.pop("_jr", None)
    for c, v in failing:                        # any other: the FEA's, or a check with no thickness to offer
        if c["name"] in covered:
            continue
        fea = L.judged_by(run, c) == "fea"          # "works hardest in" is the FEA's to say (#318 re-check)
        where = (c.get("fea") or {}).get("in") if fea else None
        rows.append(_spoke(_row(f"fails:{c['name']}", f"It doesn't hold {c['name']}: {_x(c['safety'], need)} where it needs {need:g}×"
                                              + (f"; it works hardest in the {where}" if where else "") + note([c["name"]]),
                         [_choice(f"Make the {where} stronger: thicker, or with a rib or a brace" if where
                                  else "Make it stronger where it fails", DESIGNER, _designer_cost(name)),
                          _choice("Ask it to hold less: a lighter load in its loads()", DESIGNER, _designer_cost(name))], pid),
                           [c["name"]], f"'{c['name']}'"))
    for c, v in said:                           # what Caliper can't fix by itself: said apart, never ticked
        b = verdicts.wood_brace(run, c)          # joints #311 didn't reach, as the card reads them (#318 re-check)
        if b:
            words = joint_said(b, need).strip().rstrip(".")
            limits.append(words[:1].upper() + words[1:] if b.get("names") or b.get("unchained")
                          else "Its joints aren't checked: " + words)
        if v["kind"] == "span":
            limits.append(verdicts.SPAN_WHY[:1].upper() + verdicts.SPAN_WHY[1:])
        if L.rough(run, c):
            limits.append(L.ROUGH)
    return rows, limits


def _pending(store: DesignStore, pid: str) -> dict:
    """``{case name: words}`` for each case checked at one side of an open question on the part's loads (#312): a row
    of it says it's of that value, pending the person's choice (#318 re-check)."""
    from . import construction as C
    from . import scenarios as SC

    said = SC._said(store, pid)
    if not said:
        return {}
    out = {}
    for e in SC._effective(said, C.declared(store, pid)):
        if not e.get("conflict"):
            continue
        d = e.get("design") or {}
        for r in e.get("checks") or [e["row"]]:
            design = bool(d) and r["amount"] == d.get("amount") and r["unit"] == d.get("unit") \
                and not str(r["name"]).endswith("(yours)")
            amount = f"{SC._num(r['amount'])} {r['unit']}"
            out[SC.name(r)] = (f"of the design's {amount}, pending your choice" if design
                               else f"of yours, {amount}, pending your choice")
    return out


def _racking() -> Optional[str]:
    try:
        from .joint_check import RACKING_SAID
    except ImportError:  # pragma: no cover — before #313
        return None
    return RACKING_SAID


def _more(jr: dict) -> tuple:
    """How much a joint row's fix asks, to keep the one every case passes at: its screws, then the lower it'd read."""
    m = jr.get("more_screws") or {}
    return (m.get("to") or 0, -(m.get("reads") or 0.0))


def _joint_choices(jr: dict, name: str) -> list[dict]:
    """A joint's fix: only what the check credits (#344, the foreman: a glue block isn't, nor a dado or a rabbet). Where
    screws take it past, the count the governing number asks, as the ``JOINTS`` entry that declares it, and what it
    would read (said to crowd the edge where they come that close); else by how it gives (#301)."""
    import json

    between, cost = jr["between"], _designer_cost(name)
    more = jr.get("more_screws")
    if more:
        return [_choice(f"{more['to']} #8 screws where {between} meet, {more['more']} more: its JOINTS entry "
                        f"{json.dumps(more['entry'])}; it would read {more['reads']:g}×"
                        + (f" ({more['crowded']})" if more.get("crowded") else ""), DESIGNER, cost, entry=more["entry"])]
    piece = (jr.get("pieces") or [""])[0]
    by = {"bearing": f"More bearing where {between} meet: a thicker piece, or a cleat under it",
          "net section": f"Leave more of the {piece} past its notch: a shallower notch, or a wider piece"}
    first = by.get(jr.get("mode"))
    return ([_choice(first, DESIGNER, cost)] if first else []) + [
        _choice("Ask it to hold less: a lighter load in its loads()", DESIGNER, cost)]


def _scenario_rows(store: DesignStore, pid: str) -> list[dict]:
    """The part's edited loads (#312): an open question (the design changed a case under an edit) to settle, and a case
    turned off, so nothing checks it. Each a change to its loads, no designer."""
    from . import construction as C
    from . import scenarios as SC

    said = SC._said(store, pid)
    if not said:
        return []
    out = []
    for e in SC._effective(said, C.declared(store, pid)):
        if e.get("conflict"):
            q = SC._asked(e)
            choices = ([_choice("Take the design's", LOADS, LOADS_COST, scenario=e["of"], take="design")]
                       if e.get("design") else [])
            choices.append(_choice("Keep mine", LOADS, LOADS_COST, scenario=e["of"], take="mine"))
            out.append({**_row(f"asked:{e['of']}", q[:1].upper() + q[1:], choices, pid), "measured": False,
                        "badge": "your loads", "ticked": False})        # never settles itself untouched (#318)
        elif not e["row"].get("on", True):
            nm = SC.name(e["row"])
            out.append({**_row(f"off:{e.get('of') or nm}", f"'{nm}' is turned off, so nothing checks it",
                               [_choice("Turn it back on", LOADS, LOADS_COST, scenario=e.get("of") or nm, take="on")], pid),
                        "measured": False, "badge": "your loads"})       # the person's own edit, not a measurement
    return out


def _finding_rows(store: DesignStore, pid: str, name: str) -> list[dict]:
    """The after-build findings (#238 slice A) that name this part: measured, each its proposed change."""
    from . import review

    try:
        found = review.findings(store)
    except Exception:  # noqa: BLE001 — the list goes without them, and says nothing it didn't measure
        return []
    out = []
    for f in found.get("findings") or []:
        if pid not in (f.get("parts") or []) or not f.get("measured"):
            continue
        said = f["said"][:1].upper() + f["said"][1:]
        # by what it is, never its place in the list: one fixed moves the rest up (#300 slice B: it read "fixed")
        out.append(_row(f"finding:{f.get('kind')}:{f.get('id') or f['said']}", said,
                        [_choice(f["fix"].rstrip("."), DESIGNER, _designer_cost(name))], pid))
    return out


#: A reading's row id starts so (#238 slice B): Fix these says it done, never fixed, as nothing measures it.
READING = "reading:"


def _reading_rows(store: DesignStore, pid: str, name: str) -> list[dict]:
    """The last Review it's readings (#238 slice B) that name this part: Claude's reading, never measured, each its proposed
    change. A reading of a version this part has moved on from says so ("read on v3; it's changed since")."""
    from . import assess

    rec = assess.latest(store)
    if not rec:
        return []
    moved = assess.stale(store, rec)
    out = []
    for r in rec.get("readings") or []:
        if pid not in (r.get("parts") or []):
            continue
        was = moved.get(pid)
        badge = ("Claude's reading" + (f" · read on v{was}; it's changed since" if was else "")
                 + (f" · may repeat what's measured: {r['may_repeat']}" if r.get("may_repeat") else ""))
        mine = [pc for pc in r.get("pieces") or [] if pc.get("part") == pid]   # the pieces it names here (#368 re-check)
        problem = r["said"][:1].upper() + r["said"][1:] + (f" ({', '.join(pc['name'] for pc in mine)})" if mine else "")
        out.append({**_row(f"{READING}{rec.get('n')}:{r.get('id')}", problem,
                           [_choice(r["fix"].rstrip("."), DESIGNER, _designer_cost(name))], pid),
                    "measured": False, "badge": badge, "stale": bool(was),
                    **({"pieces": [pc["piece"] for pc in mine]} if mine else {})})
    return out


#: A round check's own fix, where the card's (``answers.fix_for``: the shape or its pieces) isn't it (CALI-238, #406).
ROUND_FIX = {
    "shell_in_walls": "Put each wall beam shell() gives in its wall, of that wall's core, thickness and skins",
    "keeps_clear": "Keep the outside out of what keeps() holds clear: move or shrink the shape, or move the box it keeps",
}
#: Round checks a strength run's own row already speaks for, or that only warn: never a second row.
_SAID_BY_RUN = {"construction_volume": "filled", "construction_covers": "filled"}
_ONLY_WARN = {"loads_edge"}


def _round_rows(store: DesignStore, pid: str, name: str, have: list[dict]) -> list[dict]:
    """The checks that failed in the designer's round on the part as built, each a row (CALI-238, #406: the card said
    them, Things to fix didn't): its words, as the card says them, and its fix. Measured, so after Fix these it reads
    Fixed when the check passes on the new version."""
    import re

    from . import answers, consistency

    try:
        got = consistency.checked(store, pid)
    except Exception:  # noqa: BLE001 — a part that can't be checked lists nothing it didn't measure
        return []
    ids = {r["id"] for r in have}
    out = []
    for r in got:
        if r.status not in ("fail", "error") or r.id in _ONLY_WARN or _SAID_BY_RUN.get(r.id) in ids:
            continue
        detail = (r.detail or r.expr or r.id).strip()
        if r.id.startswith("construction_"):
            problem = f"Its 3D shape and its pieces don't match: {detail}"
            said = answers.fix_for(r.id, detail, pid)
            fix = (re.findall(r'"([^"]+)"', said) or [said])[0]          # the first of the card's own words
        else:
            first = detail.split(" ", 1)[0]
            problem = detail if "_" in first else detail[:1].upper() + detail[1:]   # an id stays as it's written
            fix = ROUND_FIX.get(r.id) or f"Make it pass its check {r.id.replace('_', ' ')}"
        out.append(_row(f"check:{r.id}", problem, [_choice(fix, DESIGNER, _designer_cost(name))], pid))
    return out


def listed(store: DesignStore, state: dict, pid: str, *, findings: bool = True) -> dict:
    """``{"part", "rows", "limits"}``: the part's things to fix, measured, each ``{id, problem, choices, part,
    measured}`` with its choices ``{fix, kind, cost, ...}`` (a number's ``param``, ``value``, ``unit``; a check's
    ``spacing_mm``), the first the one proposed; and its known limits, in words, each once."""
    from . import part_rules

    p = next(x for x in state["parts"] if x["id"] == pid)
    if p.get("role") == "fixed" or not store.is_scripted(pid):
        return {"part": pid, "rows": [], "limits": [], "counts": counts([])}
    name = _part_name(p)
    rows = [_row(f"rule:{r.get('id') or r.get('expr') or r['said']}", f"It breaks its rule {r['said']}",
                 [_choice(f"Make it keep its rule {r['said']}", DESIGNER, _designer_cost(name))], pid)
            for r in part_rules.failing(p.get("rules") or [])]      # by the rule's own id, never its place (#322)
    limits: list[str] = []
    runs = [r for r in state.get("load_runs") or [] if r["part"] == pid]
    if runs:
        got, lim = _run_rows(store, p, runs[0], name)
        rows += got
        limits += lim
    rows += _scenario_rows(store, pid)           # its edited loads' questions, and cases turned off (#312)
    rows += _round_rows(store, pid, name, rows)  # what failed in the designer's round on it as built (#406)
    if findings:
        rows += _finding_rows(store, pid, name)
        rows += _reading_rows(store, pid, name)       # Claude's reading, on the person's press, badged (#238 slice B)
    return {"part": pid, "rows": rows, "limits": list(dict.fromkeys(limits)), "counts": counts(rows)}


def counts(rows: list[dict]) -> dict:
    """The list's counts, said apart (#368 review: the header counted Claude's readings as "measured wrong"):
    ``{"measured", "readings", "other"}``. ``measured``: rows a measurement made; ``readings``: Claude's; ``other``: the
    person's own (their loads). The header says "1 measured wrong · 2 of Claude's readings"."""
    readings = sum(1 for r in rows if str(r.get("id", "")).startswith(READING))
    measured = sum(1 for r in rows if r.get("measured") is not False)
    return {"measured": measured, "readings": readings, "other": len(rows) - measured - readings}
