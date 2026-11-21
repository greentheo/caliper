"""CALI-189 (#300) slice B — Fix these: the rows the person ticked under Things to fix, done, then measured again.

The list is :mod:`fixes`' (measured, no model call). Here, what pressing Fix these does:

1. **The cost, said first** (:func:`plan`): "1 number change, at once; 1 designer edit on the stool (one Claude call);
   then a check, about 2 min". Pressing the button is the person's own word for any designer call it names.
2. **Numbers first**, through the Parameters route (#267, ``params.set_values``): all of them at once, no model call.
3. **The edited loads** (#312): an open question settled, a case turned back on, through ``scenarios.put``.
4. **The designer's items, as one revise of the part**: the ticked fixes, the reworded ones and the person's own, in
   one message (#241's path, one part at a time).
5. **The strength check again** where the part changed or a check was ticked, finer where that was the fix.
6. **The list again**: each row **Fixed** only where a measurement says so (it's gone from a list read after the part's
   own check of this version, or from the measurement that made it), **Still open** where it's there, or **Not done**
   where the designer left the part as it was. The person's own words are never "fixed": they're done, not measured.

Every row is read back from the server's own list by its id: the page sends which rows and which choice, never a
number or a fix's words but the person's own.
"""

from __future__ import annotations

from typing import Optional

from .design import DesignStore
from .fixes import CHECK, DESIGNER, LOADS, NUMBER, READING, listed

#: A row whose measurement comes from the strength check: gone from the list only means fixed after a fresh one.
_FROM_CHECK = ("stale", "unsized", "finer", "filled", "plate:", "buckling:", "joint:", "fails:")


def _state(store: DesignStore) -> dict:
    from . import design_api

    return design_api.design_state(store)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _spoken(row: dict) -> dict:
    return {k: row[k] for k in ("cases", "what") if k in row}


#: A check-made row's kind (its id's head), in words: what was fixed, and what a case still fails on (#322).
_KIND = {"plate": "plate", "joint": "joint", "buckling": "buckling", "fails": "check"}


def _moved(item: dict, run: Optional[dict], rows: list[dict]) -> Optional[dict]:
    """Whether a check-made row gone from the list is fixed (#322, the foreman's rule): only where every case it spoke
    for is in the fresh run and passes. None: fixed, nothing to add. Else ``{"status", "why"}``:

    - a case not in the fresh run: still open, "'…' isn't checked any more";
    - a case failing: by the row's own measurement there, fixed (and what still fails it, said) or still open (its
      number, said);
    - its own not measured there: still open, "it's measured as '…' now" where a plate or buckling row of its kind
      speaks for the case (a piece renamed is a new id), else "not measured as fixed"."""
    from . import verdicts

    spoke = item.get("cases") or []
    if not spoke:
        return None
    by = {c.get("name"): c for c in (run or {}).get("cases") or []}
    need = (run or {}).get("min_safety")
    missing = [n for n in spoke if n not in by]
    if missing:
        return {"status": "still open",
                "why": " and ".join(f"'{n}'" for n in missing) + (" aren't" if len(missing) > 1 else " isn't")
                + " checked any more"}
    failing = {n for n in spoke if not verdicts.meets(by[n].get("safety"), need)["counts_as_pass"]}
    if not failing:
        return None
    kind = str(item.get("id") or "").split(":")[0]
    covers = [r for r in rows if set(r.get("cases") or []) & failing]
    # the row's own measurement in the fresh run first, wherever it's found (#322, caliper-reviewer at 28b0707: the left
    # front joint fixed at 2.4x read "still open: measured as" the right one, which governs at 1.62x); the list makes a
    # plate row only where the plate governs (reviewer-2 at 03a312a: the step's plate at 1.91x read "fixed")
    key = str(item.get("id") or "").split(":", 1)[1] if ":" in str(item.get("id") or "") else ""
    own = [_own(kind, key, by[n]) for n in sorted(failing)]
    if any(s is None for s in own):                  # not measured there: renamed, or no longer checked
        same = next((r for r in covers if str(r["id"]).split(":")[0] == kind), None)
        if same is not None and kind in ("plate", "buckling"):      # a panel by another name: the other of a pair of
            return {"status": "still open",                         # joints isn't a rename
                    "why": f"it's measured as '{same.get('what') or same['problem']}' now"}
        return {"status": "still open", "why": "not measured as fixed"}
    worst = min(own)
    if not verdicts.meets(worst, need)["counts_as_pass"]:
        from .fixes import _x

        what = item.get("what") or f"the {key}"
        mine = what if kind in ("joint", "fails") else f"{what}'s {_KIND.get(kind, 'check')}"
        return {"status": "still open", "why": f"measured: {mine} is still {_x(worst, need)} where it needs {need:g}×"}
    other = covers[0] if covers else None
    okind = str(other["id"]).split(":")[0] if other is not None else ""
    said = (other.get("what") or other["problem"]) if other is not None else ""
    on = ("" if other is None or okind == "fails" else       # a case's own row: the case, said already
          f": {said}" if okind == "joint" else f": {said}'s {_KIND.get(okind, 'check')}")   # a joint's what says joint
    return {"status": "fixed", "why": f"fixed (the {_KIND.get(kind, 'check')}), and the case still fails{on}"}


def _own(kind: str, key: str, case: dict) -> Optional[float]:
    """A row's own measurement in a fresh case (#322): the plate check's safety across the grain for that panel, the
    joint's by its pieces, the panel's buckling, or a case's own. None where it isn't measured there (a piece renamed)."""
    if kind == "plate":
        pl = case.get("plate") or {}
        return pl.get("safety_across") if pl.get("piece") == key and pl.get("done") else None
    if kind == "joint":
        return next((jr.get("safety") for jr in (case.get("joints") or {}).get("rows") or []
                     if "|".join(jr.get("pieces") or []) == key), None)
    if kind == "buckling":
        return next((b.get("safety") for b in case.get("buckling") or [] if b.get("piece") == key and b.get("done")),
                    None)
    if kind == "fails":
        return case.get("safety")
    return None


def _said_number(c: dict) -> str:
    """A number change at Go ahead: "t: make the top from 5/8 in", or the choice's own words where they name the number
    already (#322, caliper-reviewer at 28b0707: "fillet_r: remove the inside corner fillet strips: fillet_r to 0")."""
    words = c["fix"][:1].lower() + c["fix"][1:]
    return words if f"{c['param']} to " in c["fix"] else f"{c['param']}: {words}"


def plan(store: DesignStore, state: dict, pid: str, picked: list[dict], own: Optional[list[dict]] = None) -> dict:
    """What Fix these will do, read from the server's own list: ``{"numbers", "loads", "designer", "check", "said",
    "designer_call", "gone"}``. ``picked``: ``[{"id", "choice", "words"?}]``; ``own``: ``[{"fix"}]`` (the person's)."""
    from .fixes import _part_name

    got = listed(store, state, pid)
    by = {r["id"]: r for r in got["rows"]}
    p = next(x for x in state["parts"] if x["id"] == pid)
    numbers, loads, designer, checks, gone = [], [], [], [], []
    for pk in picked or []:
        r = by.get(pk.get("id"))
        if r is None:
            gone.append(pk.get("id"))                     # not on the list now: nothing to do for it
            continue
        words = str(pk.get("words") or "").strip()
        if words:                                         # reworded: the person's words, the designer's to do
            designer.append({"id": r["id"], "fix": words, "own": True, "problem": r["problem"], **_spoken(r)})
            continue
        k = int(pk.get("choice") or 0)
        c = r["choices"][k if 0 <= k < len(r["choices"]) else 0]
        item = {"id": r["id"], "fix": c["fix"], "problem": r["problem"], **c, **_spoken(r)}
        {NUMBER: numbers, LOADS: loads, DESIGNER: designer, CHECK: checks}.get(c["kind"], designer).append(item)
    same = []                                            # a second row on a parameter: one change, the first's value
    seen_params: dict = {}
    for c in list(numbers):
        if c["param"] in seen_params:
            numbers.remove(c)
            same.append({**c, "first": seen_params[c["param"]]})
        else:
            seen_params[c["param"]] = c
    for o in own or []:
        words = str(o.get("fix") or "").strip()
        if words:
            designer.append({"id": None, "fix": words, "own": True, "problem": None})
    changes = bool(numbers or loads or designer)
    loaded = bool(p.get("loads"))
    check = None
    if checks or (changes and loaded):                   # the check again: where the part changed, or it was ticked
        spacing = next((c.get("spacing_mm") for c in checks if c.get("spacing_mm")), None)
        runs = [r for r in state.get("load_runs") or [] if r["part"] == pid]
        secs = (runs[0].get("seconds") or 0) if runs else 0
        finer = next((r.get("finer") or {} for r in runs[:1]), {}) if spacing else {}
        check = {"spacing_mm": spacing, "minutes": (finer.get("minutes") if spacing else (secs / 60 if secs else None))}
    from .fixes import _check_cost

    parts = []
    if numbers:                                          # what each moves, said at Go ahead (#322 review)
        parts.append(f"{_plural(len(numbers), 'number change', 'number changes')}, at once ("
                     + "; ".join(_said_number(c) for c in numbers) + ")")
    if loads:
        parts.append(f"{_plural(len(loads), 'change', 'changes')} to its loads, at once")
    if designer:
        parts.append(f"1 designer edit on the {_part_name(p)} (one Claude call)")
    if check:
        parts.append(("then " if parts else "") + _check_cost(check["minutes"], finer=bool(check["spacing_mm"])))
    picked_ids = {pk.get("id") for pk in picked or []}
    left = [r["problem"] for r in got["rows"] if r["id"].startswith("asked:") and r["id"] not in picked_ids]
    said = "; ".join(parts) or "nothing to do"
    for c in same:
        said += (f"; “{c['fix']}” isn't done: it sets {c['param']} too, and the first one's "
                 f"{c['first']['value']:g} {c['first'].get('unit') or 'mm'} goes")
    if left:                                      # an untouched question never settles itself: asked by name (#318)
        said += "; left open: " + "; ".join(q[:1].lower() + q[1:] for q in left)
    return {"numbers": numbers, "loads": loads, "designer": designer, "check": check, "gone": gone, "left": left, "same": same,
            "designer_call": bool(designer), "said": said}


def _message(name: str, designer: list[dict]) -> str:
    """The one revise, in the person's words where they gave them."""
    lines = []
    for d in designer:
        lines.append(f"- {d['fix']}" + (f" (it's measured: {d['problem']})" if d.get("problem") else ""))
    return f"Things to fix on the {name}, as the person ticked them under Will it work?:\n" + "\n".join(lines)


def _loads(store: DesignStore, pid: str, loads: list[dict]) -> None:
    """The edited loads' choices (#312), as the editor would make them, in one save."""
    from . import scenarios as SC

    got = SC.get(store, pid)
    rows = got["scenarios"]
    for item in loads:
        i = next((k for k, r in enumerate(rows) if r.get("of") == item.get("scenario")), None)
        if i is None:
            continue
        if item["take"] == "design" and rows[i].get("design"):
            rows[i] = {**rows[i]["design"], "of": rows[i].get("of")}
        elif item["take"] == "mine":
            rows[i] = {**rows[i], "keep": True}
        elif item["take"] == "on":
            rows[i] = {**rows[i], "on": True}
    SC.put(store, pid, rows, got["supports"])


def apply(store: DesignStore, pid: str, picked: list[dict], own: Optional[list[dict]] = None, *, check: bool = True,
          emit=None, stop=None) -> dict:
    """Do what :func:`plan` says, cheapest first, then measure it again: ``{"plan", "results", "version", "said"}``.
    Each result ``{"id", "fix", "status": fixed | still open | not done | done, not measured, "why"}``."""
    from . import chat, load_study, params

    def say(kind: str, text: str) -> None:
        if emit:
            emit(kind, text)

    state = _state(store)
    p = plan(store, state, pid, picked, own)
    name = next(x for x in state["parts"] if x["id"] == pid)
    from .fixes import _part_name

    name = _part_name(name)
    done_numbers = done_loads = False
    if p["numbers"]:
        say("fixing", "the numbers, through Parameters")
        seen, changes = set(), []
        for c in p["numbers"]:                           # one change per parameter: the first row's value
            if c["param"] not in seen:
                seen.add(c["param"])
                changes.append({"name": c["param"], "value": c["value"], "unit": c.get("unit") or "mm"})
        params.set_values(store, pid, changes)
        done_numbers = True
    if p["loads"]:
        say("fixing", "its loads")
        _loads(store, pid, p["loads"])
        done_loads = True
    if stop:
        stop()
    designer_changed = None
    if p["designer"]:
        say("fixing", "the designer's edits, in one revise")
        before = store.design.part(pid).version
        # the same code back writes no version (#322 review: the card was left "of v7, not this version" for nothing)
        res = chat.refine_part(store, pid, _message(name, p["designer"]), on_event=None, keep_same=False)
        store = DesignStore.load(store.root)
        designer_changed = bool(res.ok) and store.design.part(pid).version != before
    checked, check_why = False, ""
    if check and p["check"] and (done_numbers or done_loads or designer_changed or not p["designer"]):
        say("checking", "the strength check again")
        try:
            load_study.study(store, pid, **({"spacing": p["check"]["spacing_mm"]} if p["check"]["spacing_mm"] else {}))
            checked = True
        except Exception as e:  # noqa: BLE001 — said in each row it leaves unmeasured, never a crash of the fix
            check_why = f"not checked again: {type(e).__name__}"
        store = DesignStore.load(store.root)
    now = _state(store)
    rows_after = listed(store, now, pid)["rows"]
    after = {r["id"] for r in rows_after}
    run_after = next((r for r in now.get("load_runs") or [] if r["part"] == pid), None)
    results = []
    for item in p["numbers"] + p["loads"] + p["designer"] + [{"id": r, "fix": None, "gone": True} for r in p["gone"]] \
            + [{**c, "same": True} for c in p["same"]]:
        rid = item.get("id")
        if item.get("same"):
            results.append({"id": rid, "fix": item["fix"], "status": "not done",
                            "why": f"it sets {item['param']} too: the first one's value went"})
            continue
        if item.get("gone"):
            results.append({"id": rid, "fix": None, "status": "gone", "why": "it wasn't on the list any more"})
            continue
        if item in p["designer"] and designer_changed is False:
            results.append({"id": rid, "fix": item["fix"], "status": "not done", "why": "the designer left the part as it was"})
            continue
        if item.get("own") and rid is None:                # the person's own: done, but nothing measures it
            results.append({"id": rid, "fix": item["fix"], "status": "done, not measured",
                            "why": "your words: nothing in the list measures them"})
            continue
        if str(rid).startswith(READING):                # Claude's reading: nothing measures it, so never fixed (#238 B)
            results.append({"id": rid, "fix": item["fix"], "status": "done, not measured",
                            "why": "Claude's reading: nothing measures it. Review again to have it read"})
            continue
        from_check = str(rid).startswith(_FROM_CHECK)
        if rid in after:
            results.append({"id": rid, "fix": item["fix"], "status": "still open", "why": "it's still measured so"})
        elif from_check and not checked:
            results.append({"id": rid, "fix": item["fix"], "status": "still open",
                            "why": check_why or "not checked again, so not measured as fixed"})
        elif from_check and (moved := _moved(item, run_after, rows_after)) is not None:
            results.append({"id": rid, "fix": item["fix"], **moved})
        else:
            results.append({"id": rid, "fix": item["fix"], "status": "fixed", "why": "measured: it's off the list now"})
    n = {s: sum(1 for r in results if r["status"] == s) for s in ("fixed", "still open", "not done")}
    said = "; ".join(f"{v} {k}" for k, v in n.items() if v) or "nothing done"
    return {"plan": p, "results": results, "version": store.design.part(pid).version, "said": said, "checked": checked}
