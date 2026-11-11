"""CALI-35 (#3b) — a reviewed plan's parts, built one at a time, in its build order.

#3a planned a design of several parts and stopped for the person to review it. Build it on a reviewed plan now
authors each part to be made, mounted-on first:

- its designer sees the skeleton's numbers and the parts already built, where they are
  (:meth:`DesignStore.prompt_context`);
- the plan's rules and mates between it and the parts already built are measured each round, so one that fails fails
  the round, and the designer fixes it as it fixes any failing measurement;
- a part that still won't build leaves the parts before it; the reply names it and why, and Build it again carries on
  from it. A part the person has (``role: fixed``) isn't designed.

Each step is narrated, so the viewport fills as it goes. The skeleton's numbers driving the parts (and rebuilding
them when one changes) is #3c.
"""

from __future__ import annotations

from typing import Callable, Optional

from . import chat
from . import plan as P
from . import verdicts
from .design import DesignStore


def interfaces(store: DesignStore, pid: str, built: dict) -> Callable:
    """The plan's mates and rules between ``pid`` and the parts already built (``{id: Geometry}``), measured on a
    candidate geometry for ``pid`` with the skeleton's values: what fails its round. A rule over a part not built
    yet waits for that part; it isn't measured here."""
    from .assembly import Assembly, _names, evaluate_assembly

    here = {pid, *built}
    ids = {p.id for p in store.assembly.parts}
    mates = [m for m in store.assembly.mates if pid in m.between and set(m.between) <= here]
    rules = [a for a in store.assembly.assertions
             if pid in _names(a.expr) and (_names(a.expr) & ids) <= here]
    sub = Assembly(name=store.assembly.name, parts=[p for p in store.assembly.parts if p.id in here],
                   mates=mates, assertions=rules)
    values = P.skeleton_values(store.design.skeleton)

    def check(geometry):
        return evaluate_assembly(sub, base_dir=store.root, parts={**built, pid: geometry}, values=values).results
    return check


#: Designer tries a part gets: the plan's review says the total before Build it (#135 review), and no run exceeds it.
ROUNDS = 2
#: As a first build (CALI-157): the first try and one repair, and only for what stops the part being shown right.
REPAIRS = frozenset({"construction_covers", "construction_volume"})


def cost(plan) -> str:
    """What building a plan may take, said before Build it: "3 parts to make, up to 4 designer tries each"."""
    n = len(P.buildable(plan))
    return f"{n} part{'s' if n != 1 else ''} to make, up to {ROUNDS} designer tries each (at most {n * ROUNDS})"


def plainly(error: str) -> str:
    """A build error as a person reads it (#135 review): the reason's last line ("the hub won't fit the shaft"),
    never a traceback or a server path."""
    import re

    lines = [ln.strip() for ln in (error or "").splitlines() if ln.strip()]
    last = lines[-1] if lines else "it never built"
    last = re.sub(r"^[A-Za-z_.]*(Error|Exception|Failure)\b:?\s*", "", last) or last
    return last if not re.search(r"(/|\\)[\w.-]+(/|\\)", last) else "it raised an error while building"


def _marks(mine: list) -> tuple[str, str]:
    """A built part's rules as the reply marks them, from the one verdict (#132): each rule's mark ("✓", "✗", or "·"
    for one that waits; an error is a fail), and the part's own mark from its report's verdict. A mark only for what
    was measured (#135 review): nothing measured, no head mark."""
    statuses = ["fail" if r.status == "error" else r.status for r in mine]
    marks = ", ".join(f"{r.id} {_mark(verdicts.check(s))}" for r, s in zip(mine, statuses))
    head = _mark(verdicts.report({"results": [{"status": s} for s in statuses]})) if mine else ""
    return marks, head


def _mark(v: dict) -> str:
    """A verdict as the build's reply marks it: ✓ holds, ✗ fails, · anything not yet settled (a rule that waits)."""
    return "✓" if v["kind"] == "holds" else "✗" if v["kind"] == "fails" else "·"


def _unheld(store: DesignStore, built: dict) -> bool:
    """A built part that says what it must hold, with no strength check of this version."""
    from . import load_study

    for pid in built:
        entry = store.design.part(pid)
        if entry and store.is_scripted(pid) and "def loads(" in store.read_script(pid) and not any(
                r.get("version") == entry.version for r in load_study.list_runs(store, pid)):
            return True
    return False


def _unscored(store: DesignStore) -> bool:
    from . import scorecard

    versions = {p.id: p.version for p in store.design.parts}
    cards = scorecard.list_cards(store, 1)
    return not cards or cards[0].get("versions") != versions


def build(store: DesignStore, steps: dict, emit: Callable, *, author=None, client=None, use_llm: bool = True,
          max_rounds: int = ROUNDS) -> dict:
    """Build the saved plan's parts in order. Returns the first run's result: ``plan`` is ``built`` when every
    part to be made is, ``stopped`` (with ``part``, the one that wouldn't build) when one isn't."""
    plan = P.load(store)
    by = {p.id: p for p in plan.parts}
    order = P.order(plan)

    def forward(ev):
        emit(ev.kind, ev.text, **ev.data)

    said, built, kept, failed = [], {}, [], None
    for pid in order:
        p, name = by[pid], pid.replace("_", " ")
        if p.role == "fixed":
            said.append(f"- the {name}: yours, not designed")
            continue
        entry = store.design.part(pid)
        if entry is not None and entry.version:         # built on an earlier Build it: kept, not designed again
            built[pid] = store.part_geometry(pid)
            kept.append(pid)
            said.append(f"- the {name}: built before, kept")
            continue
        emit("step", f"Building the {name}", step="build", part=pid)
        check = interfaces(store, pid, built)
        res = chat.author_part(store, pid, p.what + (f" ({p.made})" if p.made else ""), author=author,
                               client=client, use_llm=use_llm, on_event=forward, promote_feedback=False,
                               max_rounds=max_rounds, interfaces=check, repair_only=REPAIRS)
        if not res.version:
            failed = (pid, plainly(res.error or "it never built"))
            # the whole text (its traceback) goes to the log, never the reply (#135 review)
            store.append_log({"kind": "firstrun", "action": "failed", "part": pid, "error": res.error})
            break
        built[pid] = store.part_geometry(pid)
        store.append_log({"kind": "firstrun", "action": "built", "part": pid, "version": res.version})
        mine = [r for r in check(built[pid])] if res.part_report is not None else []
        marks, head = _marks(mine)
        said.append(f"- the {name}: built" + (f" {head}" if head else "") + (f" ({marks})" if marks else ""))
        emit("step", f"The {name}: built" + (f" ({marks})" if marks else ""), step="built", part=pid)

    made = [pid for pid in order if by[pid].role != "fixed"]
    status = "stopped" if failed else "built"
    store.design.plan = {**store.design.plan, "status": status}
    store.save()
    report, errors = chat._measure_design(store)
    # a measurement that threw is no pass (rule 6, #135 review): "not checked", with why, and the build isn't ok
    unmeasured = plainly(errors.get("<design>")) if report is None and errors.get("<design>") else ""
    whole = (report.said()[:1].upper() + report.said()[1:] + ".") if report is not None else ""
    if failed:
        pid, why = failed
        before = [x.replace("_", " ") for x in made[:made.index(pid)]]
        reply = (f"I couldn't build the {pid.replace('_', ' ')}: {why.strip()}.\n\n"
                 + (f"The parts before it stay ({', '.join(before)}). " if before else "")
                 + "Build it again to retry it, change the plan, or carry on without it.")
    else:
        # what wasn't checked, said: design checks are geometry, never whether it holds (#135 review)
        unchecked = [x for x in ("whether it holds (Check it holds)" if _unheld(store, built) else "",
                                 "the scorecard" if _unscored(store) else "") if x]
        reply = (f"I built the plan's {len(made)} parts, in order:\n" + "\n".join(said)
                 + (f"\n\nThe design checks: {report.said()}." if report is not None else
                    f"\n\nThe design checks: not checked: {unmeasured}." if unmeasured else "")
                 + (f"\n\nNot checked yet: {' and '.join(unchecked)}. Run *Will it work?* next." if unchecked else ""))
    steps["plan"] = f"{status}: {len(built)} of {len(made)} parts"
    ok = not failed and not unmeasured and (report is None or verdicts.report(report.to_dict())["counts_as_pass"])
    # the log says what the result says (#135 review nit): a measurement that threw is no ok there either
    store.append_log({"kind": "reply", "action": "plan", "ok": ok, "reply": reply, "firstrun": True})
    emit("step", "Done", step="done")
    return {"part": failed[0] if failed else (made[-1] if made else None), "ok": ok, "steps": steps,
            "reply": reply, "plan": status, "built": list(built)}
