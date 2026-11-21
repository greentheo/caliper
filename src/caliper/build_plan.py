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
    from . import skeleton

    def check(geometry, script: str = ""):
        got = evaluate_assembly(sub, base_dir=store.root, parts={**built, pid: geometry}, values=values).results
        if script and store.design.skeleton:   # it reads the plan's shared sizes, never its own (CALI-162, #240)
            got.append(skeleton.shadows(pid, script, store.design.skeleton,
                                        [p["id"] for p in (store.design.plan or {}).get("parts") or []]))
        return got
    return check


#: Designer tries a part gets: the plan's review says the total before Build it (#135 review), and no run exceeds it.
ROUNDS = 2
#: As a first build (CALI-157): the first try and one repair, and only for what stops the part being shown right.
REPAIRS = frozenset({"construction_covers", "construction_volume", "skeleton_shadow"})   # its own sizes: fixed (#240)


def _said(pid: str) -> str:
    return pid.replace("_", " ")


def _listing(xs: list[str]) -> str:
    return ", ".join(xs[:-1]) + f" and {xs[-1]}" if len(xs) > 1 else (xs[0] if xs else "")


def _top(plan, pid: str) -> Optional[str]:
    """The group a part is directly in, or None (CALI-36, #17): two deep, the platform and the box under a camper keep
    their own heads (#415 review)."""
    chain = P.group_of(plan, pid)
    return chain[-1] if chain else None


def _short(pid: str, gid: Optional[str]) -> str:
    """A part said within its group: the box's floor, not its box floor."""
    words = pid.split("_")
    lead = gid.split("_") if gid else []
    if lead and words[:len(lead)] == lead and len(words) > len(lead):
        words = words[len(lead):]
    return " ".join(words)


def _stopped(plan, pid: str, why: str, made: list, built: dict) -> str:
    """What a stop says in a plan in groups (#415 review): the part and its group, what stays (a group whole, or the parts
    of the stopped group built before it), and what isn't built yet."""
    g = _top(plan, pid)
    first = f"I couldn't build the {_said(pid)}" + (f", in the {_said(g)}" if g else "") + f": {why.strip()}."
    keys = list(dict.fromkeys(_top(plan, x) for x in made))
    whole, partial = [], []
    for k in keys:
        mine = [x for x in made if _top(plan, x) == k]
        done = [x for x in mine if x in built]
        if k is None:
            whole += [f"the {_said(x)}" for x in done]
        elif done and len(done) == len(mine):
            whole.append(f"the {_said(k)}'s {len(mine)} part{'s' if len(mine) != 1 else ''}")
        elif done:
            partial.append(f"the {_said(k)}'s {_listing([_short(x, k) for x in done])}")
    rest = [f"the {_said(x)}" for x in made if x not in built and x != pid]
    said = ""
    if whole or partial:
        stays = (_listing(whole) + (", and " + _listing(partial) if partial else "") if whole else _listing(partial))
        said = stays[:1].upper() + stays[1:] + " stay"
    if rest:
        said += ("; " if said else "") + f"{_listing(rest)} {'aren' if len(rest) > 1 else 'isn'}'t built yet"
    return first + "\n\n" + (said + ". " if said else "") + "Build it again to retry it, change the plan, or carry on without it."


def cost(plan) -> str:
    """What building a plan may take, said before Build it: "3 parts to make, up to 4 designer tries each"; a plan in
    groups says each group's share first (CALI-36, #17): "5 parts to make (the platform: 2, the box: 2, and 1 on its
    own), …"."""
    make = P.buildable(plan)
    n = len(make)
    per = ""
    if plan.groups:
        counts: dict = {}
        for pid in [x for x in P.order(plan) if x in make]:
            counts[_top(plan, pid)] = counts.get(_top(plan, pid), 0) + 1
        loose = counts.pop(None, 0)
        per = " (" + ", ".join(f"the {_said(g)}: {c}" for g, c in counts.items()) + (
            f", and {loose} on its own" if loose else "") + ")"
    return f"{n} part{'s' if n != 1 else ''} to make{per}, up to {ROUNDS} designer tries each (at most {n * ROUNDS})"


def told(plan, pid: str) -> str:
    """What a part's designer is told of its group (CALI-36, #17): which group it's in, its other parts, and what the
    group sits on, built before it. '' for a part in none. The numbers they share are the skeleton's, as for any part."""
    chain = P.group_of(plan, pid)
    if not chain:
        return ""
    g = P._group(plan, chain[-1])
    others = [f"the {_said(x)}" for x in P.group_parts(plan, g.id) if x != pid]
    line = (f"This part is in the {_said(g.id)}" + (f" ({g.what.strip().rstrip('.')})" if g.what.strip() else "")
            + (f", part of the {_said(chain[0])}" if len(chain) > 1 else "")
            + (f", with {_listing(others)}" if others else "") + ".")
    under = [m for gid in chain for m in P._group(plan, gid).mounts_on]
    if under:
        parts = [f"the {_said(x)}" for m in under for x in (P.group_parts(plan, m) if P._group(plan, m) else [m])]
        line += (f" The {_said(g.id)} sits on " + _listing([f"the {_said(m)}" for m in under])
                 + (f" ({_listing(parts)})" if parts and [f"the {_said(m)}" for m in under] != parts else "")
                 + ", built before it.")
    return "\n\n" + line + " Build only this part: the group's other parts are built on their own, from the same skeleton."


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
    from . import load_study, scenarios

    for pid in built:
        entry = store.design.part(pid)
        if entry and store.is_scripted(pid) and scenarios.says_loads(store, pid) and not any(
                r.get("version") == entry.version for r in load_study.list_runs(store, pid)):
            return True
    return False


def _unscored(store: DesignStore) -> bool:
    from . import scorecard

    versions = {p.id: p.version for p in store.design.parts}
    cards = scorecard.list_cards(store, 1)
    return not cards or cards[0].get("versions") != versions




def _section_unknown(store: DesignStore, pid: str) -> bool:
    """Whether the skeleton lacks the section of part ``pid`` that a pocket is cut to: it's known only when the plan
    names both its thickness and its height as sizes (#243 re-check: step-stool-4's ``stretcher_height`` is where it
    sits, a position, and counted as its section, so the sides were still built first)."""
    from .skeleton import known_section

    return len(known_section(store.design.skeleton, pid)) < 2


def defined_first(store: DesignStore, plan, order: list[str]) -> tuple[list[str], set]:
    """The build order, with a part that goes into another's pocket built before it when the plan can't give its size
    up front (CALI-162, #240: both sides were written before the stretcher existed, and each guessed a 2×4). Returns
    ``(order, measure)``: ``measure`` holds the parts whose section goes into the skeleton once built."""
    order, measure = list(order), set()
    for m in plan.mates:
        if m.kind != "fits_in":
            continue
        inner, outer = m.between
        if inner in order and outer in order and _section_unknown(store, inner):
            measure.add(inner)
            if order.index(inner) > order.index(outer):
                order.remove(inner)
                order.insert(order.index(outer), inner)
    return order, measure


def measure_section(store: DesignStore, pid: str, geometry) -> list[dict]:
    """Part ``pid``'s section as built, into the skeleton (:func:`skeleton.section`); [] where it can't be measured."""
    from . import skeleton

    return skeleton.section(store, pid, geometry)


def build(store: DesignStore, steps: dict, emit: Callable, *, author=None, client=None, use_llm: bool = True,
          max_rounds: int = ROUNDS) -> dict:
    """Build the saved plan's parts in order. Returns the first run's result: ``plan`` is ``built`` when every
    part to be made is, ``stopped`` (with ``part``, the one that wouldn't build) when one isn't."""
    plan = P.load(store)
    if plan.questions:                          # only the person can answer these: nothing's built over them (#371 review)
        reply = "Before I build it: " + " ".join(plan.questions) + " Say it, and I'll change the plan."
        store.append_log({"kind": "reply", "action": "plan", "ok": False, "reply": reply, "firstrun": True})
        emit("step", "Done", step="done")
        return {"part": None, "ok": False, "steps": steps, "reply": reply, "plan": "review"}
    by = {p.id: p for p in plan.parts}
    order, measure = defined_first(store, plan, P.order(plan))   # a part a pocket is cut to, first, if its size isn't planned

    def forward(ev):
        emit(ev.kind, ev.text, **ev.data)

    said, built, kept, failed = [], {}, [], None
    heads: dict = {}                                       # each group's lines, said under one head (#415 review)
    to_make = set(P.buildable(plan))
    for pid in order:
        p, name = by[pid], pid.replace("_", " ")
        top = _top(plan, pid) if plan.groups else None
        if plan.groups:
            if top not in heads:
                heads[top] = []
                if top:
                    n = len([x for x in order if _top(plan, x) == top and x in to_make])   # as the cost counts
                    emit("step", f"The {_said(top)}: {n} part{'s' if n != 1 else ''}", step="group", group=top)
            said = heads[top]
        if p.role == "fixed":
            said.append(f"- the {name}: yours, not designed")
            continue
        entry = store.design.part(pid)
        if entry is not None and entry.version:         # built on an earlier Build it: kept, not designed again
            built[pid] = store.part_geometry(pid)
            kept.append(pid)
            said.append(f"- the {name}: built before, kept")
            continue
        if p.mirror_of and p.mirror_of in built:          # flipped from its source: no designer (CALI-161, #239)
            from . import mirror

            v = mirror.make(store, pid, p.mirror_of, p.mirror_plane or "YZ", tuple(p.mirror_at or (0.0, 0.0, 0.0)),
                            feedback=f"the plan's mirror of {p.mirror_of}")
            built[pid] = store.part_geometry(pid)
            store.append_log({"kind": "firstrun", "action": "built", "part": pid, "version": v, "mirror_of": p.mirror_of})
            said.append(f"- the {name}: a mirror of the {p.mirror_of.replace('_', ' ')}, flipped, not designed")
            emit("step", f"The {name}: a mirror of the {p.mirror_of.replace('_', ' ')}", step="built", part=pid)
            continue
        emit("step", f"Building the {name}", step="build", part=pid)
        check = interfaces(store, pid, built)
        res = chat.author_part(store, pid, p.what + (f" ({p.made})" if p.made else ""), author=author, context=told(plan, pid),
                               client=client, use_llm=use_llm, on_event=forward, promote_feedback=False,
                               max_rounds=max_rounds, interfaces=check, repair_only=REPAIRS)
        if not res.version:
            failed = (pid, plainly(res.error or "it never built"))
            # the whole text (its traceback) goes to the log, never the reply (#135 review)
            store.append_log({"kind": "firstrun", "action": "failed", "part": pid, "error": res.error})
            break
        built[pid] = store.part_geometry(pid)
        store.append_log({"kind": "firstrun", "action": "built", "part": pid, "version": res.version})
        if pid in measure:                               # its section, for the parts it goes into (#240)
            got = measure_section(store, pid, built[pid])
            emit("step", (f"The {name}'s size, measured: " + ", ".join(f"{g['name'].replace('_', ' ')} {g['value']:g} mm"
                                                                       for g in got)) if got else
                 f"The {name}'s size couldn't be measured (it isn't a plain board): say its thickness and height",
                 step="measured", part=pid)
        mine = [r for r in check(built[pid])] if res.part_report is not None else []
        marks, head = _marks(mine)
        said.append(f"- the {name}: built" + (f" {head}" if head else "") + (f" ({marks})" if marks else ""))
        emit("step", f"The {name}: built" + (f" ({marks})" if marks else ""), step="built", part=pid)

    if plan.groups:                                        # each head once, its parts under it, in the order first met
        said = [line for k, lines in heads.items() for line in [f"The {_said(k)}:" if k else "On its own:", *lines]]
    made = [pid for pid in order if by[pid].role != "fixed"]
    status = "stopped" if failed else "built"
    store.design.plan = {**store.design.plan, "status": status}
    store.save()
    report, errors = chat._measure_design(store)
    # a measurement that threw is no pass (rule 6, #135 review): "not checked", with why, and the build isn't ok
    unmeasured = plainly(errors.get("<design>")) if report is None and errors.get("<design>") else ""
    whole = (report.said()[:1].upper() + report.said()[1:] + ".") if report is not None else ""
    found = None
    if failed:
        pid, why = failed
        before = [x.replace("_", " ") for x in made[:made.index(pid)]]
        reply = (_stopped(plan, pid, why, made, built) if plan.groups else
                 f"I couldn't build the {pid.replace('_', ' ')}: {why.strip()}.\n\n"
                 + (f"The parts before it stay ({', '.join(before)}). " if before else "")
                 + "Build it again to retry it, change the plan, or carry on without it.")
    else:
        # what wasn't checked, said: design checks are geometry, never whether it holds (#135 review)
        unchecked = [x for x in ("whether it holds (Check it holds)" if _unheld(store, built) else "",
                                 "the scorecard" if _unscored(store) else "") if x]
        # what's measured wrong now every part exists, before any strength check (CALI-160, #238 slice A)
        from . import review

        found = review.findings(store, report) if report is not None else None
        reply = (f"I built the plan's {len(made)} parts, in order:\n" + "\n".join(said)
                 + (f"\n\nThe design checks: {report.said()}." if report is not None else
                    f"\n\nThe design checks: not checked: {unmeasured}." if unmeasured else "")
                 + (f"\n\n{review.said(found)}" if found is not None else "")
                 + (f"\n\nNot checked yet: {' and '.join(unchecked)}. Run *Will it work?* next." if unchecked else ""))
    steps["plan"] = f"{status}: {len(built)} of {len(made)} parts"
    ok = not failed and not unmeasured and (report is None or verdicts.report(report.to_dict())["counts_as_pass"])
    # the log says what the result says (#135 review nit): a measurement that threw is no ok there either
    store.append_log({"kind": "reply", "action": "plan", "ok": ok, "reply": reply, "firstrun": True})
    emit("step", "Done", step="done")
    return {"part": failed[0] if failed else (made[-1] if made else None), "ok": ok, "steps": steps,
            "reply": reply, "plan": status, "built": list(built),
            **({"findings": found["findings"]} if not failed and found is not None else {})}
