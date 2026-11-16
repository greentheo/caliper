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

NUMBER, DESIGNER, CHECK = "number", "designer", "check"
#: What each kind of change costs, before any time is known.
NUMBER_COST = "a number change, at once"


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


def _these(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def _thicker(t: float, safety: float, need: float, power: float) -> Optional[float]:
    """The thinnest stock sheet, thicker than ``t``, whose safety clears ``need`` where safety goes as thickness to
    ``power`` (a wall's buckling load, as t³). None when no stock sheet does."""
    from .construction import THICKNESSES

    want = t * (need / safety) ** (1.0 / power) if safety > 0 else math.inf
    return next((x for x in THICKNESSES if x > t + 0.01 and x >= want - 1e-6), None)


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
                         [_choice(f"Remove the {these}", DESIGNER, _designer_cost(name)),
                          _choice(f"Give the {these} a declared size", DESIGNER, _designer_cost(name))], pid))
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
    for pick in better._sheet_picks(run, fails=True):     # a panel the plate check fails: the thinnest that holds
        param = sheet.get(pick["piece"])
        fix = f"Make the {pick['piece']} from {pick['label']} instead of {pick['label_now']}"
        choice = (_choice(fix, NUMBER, NUMBER_COST, param=param, value=pick["t_mm"], unit="mm") if param
                  else _choice(fix, DESIGNER, _designer_cost(name)))
        rows.append(_row(f"plate:{pick['piece']}", f"The {pick['piece']} fails by the plate check: about "
                                                  f"{pick['now_safety']:.1f}× where it needs {need:g}×", [choice], pid))
    for c, v in said:
        if v["kind"] != "fails" or c.get("governs") != "buckling":
            continue
        rowsb = [b for b in c.get("buckling") or [] if b.get("done") and b.get("safety") is not None]
        if not rowsb:
            continue
        b = min(rowsb, key=lambda r: r["safety"])
        t = _thicker(b["thickness_mm"], b["safety"], need, 3.0)       # its buckling load goes as t³
        choices = []
        if t is not None:
            fix = f"Make the {b['piece']} {nominal(t)} instead of {nominal(b['thickness_mm'])}"
            param = sheet.get(b["piece"])
            choices.append(_choice(fix, NUMBER, NUMBER_COST, param=param, value=t, unit="mm") if param
                           else _choice(fix, DESIGNER, _designer_cost(name)))
        choices.append(_choice(f"Add a brace to the {b['piece']}", DESIGNER, _designer_cost(name)))
        rid = f"buckling:{b['piece']}"
        if not any(r["id"] == rid for r in rows):
            rows.append(_row(rid, f"The {b['piece']} buckles under {c['name']}: about {b['safety']:.1f}× where it "
                                  f"needs {need:g}×", choices, pid))
    brace = verdicts.wood_brace(run)            # what Caliper can't fix by itself: said apart, never ticked
    if brace:                                   # its joints taken as solid wood, whatever each case reads
        limits.append("Its joints aren't checked: " + joint_said(brace, need).strip().rstrip("."))
    for c, v in said:
        if v.get("joints") and v.get("brace") and not brace:     # a pass resting on a joint nothing checks (#265)
            limits.append("Its joints aren't checked: " + joint_said(v["brace"], need).strip().rstrip("."))
        if v["kind"] == "span":
            limits.append(verdicts.SPAN_WHY[:1].upper() + verdicts.SPAN_WHY[1:])
        if L.rough(run, c):
            limits.append(L.ROUGH)
    return rows, limits


def _finding_rows(store: DesignStore, pid: str, name: str) -> list[dict]:
    """The after-build findings (#238 slice A) that name this part: measured, each its proposed change."""
    from . import review

    try:
        found = review.findings(store)
    except Exception:  # noqa: BLE001 — the list goes without them, and says nothing it didn't measure
        return []
    out = []
    for i, f in enumerate(found.get("findings") or []):
        if pid not in (f.get("parts") or []) or not f.get("measured"):
            continue
        said = f["said"][:1].upper() + f["said"][1:]
        out.append(_row(f"finding:{f.get('kind')}:{f.get('id') or i}", said,
                        [_choice(f["fix"].rstrip("."), DESIGNER, _designer_cost(name))], pid))
    return out


def listed(store: DesignStore, state: dict, pid: str, *, findings: bool = True) -> dict:
    """``{"part", "rows", "limits"}``: the part's things to fix, measured, each ``{id, problem, choices, part,
    measured}`` with its choices ``{fix, kind, cost, ...}`` (a number's ``param``, ``value``, ``unit``; a check's
    ``spacing_mm``), the first the one proposed; and its known limits, in words, each once."""
    from . import part_rules

    p = next(x for x in state["parts"] if x["id"] == pid)
    if p.get("role") == "fixed" or not store.is_scripted(pid):
        return {"part": pid, "rows": [], "limits": []}
    name = _part_name(p)
    rows = [_row(f"rule:{i}", f"It breaks its rule {r['said']}",
                 [_choice(f"Make it keep its rule {r['said']}", DESIGNER, _designer_cost(name))], pid)
            for i, r in enumerate(part_rules.failing(p.get("rules") or []))]
    limits: list[str] = []
    runs = [r for r in state.get("load_runs") or [] if r["part"] == pid]
    if runs:
        got, lim = _run_rows(store, p, runs[0], name)
        rows += got
        limits += lim
    if findings:
        rows += _finding_rows(store, pid, name)
    return {"part": pid, "rows": rows, "limits": list(dict.fromkeys(limits))}
