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


def build(store: DesignStore, steps: dict, emit: Callable, *, author=None, client=None, use_llm: bool = True,
          max_rounds: int = 4) -> dict:
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
                               max_rounds=max_rounds, interfaces=check)
        if not res.version:
            failed = (pid, res.error or "it never built")
            store.append_log({"kind": "firstrun", "action": "failed", "part": pid})
            break
        built[pid] = store.part_geometry(pid)
        store.append_log({"kind": "firstrun", "action": "built", "part": pid, "version": res.version})
        mine = [r for r in check(built[pid])] if res.part_report is not None else []
        marks = ", ".join(f"{r.id} {'✓' if r.status == 'pass' else '✗' if r.status in ('fail', 'error') else '·'}"
                          for r in mine)
        ok = all(r.status == "pass" for r in mine)
        said.append(f"- the {name}: built {'✓' if ok else '✗'}" + (f" ({marks})" if marks else ""))
        emit("step", f"The {name}: built" + (f" ({marks})" if marks else ""), step="built", part=pid)

    made = [pid for pid in order if by[pid].role != "fixed"]
    status = "stopped" if failed else "built"
    store.design.plan = {**store.design.plan, "status": status}
    store.save()
    report, _ = chat._measure_design(store)
    whole = (report.said()[:1].upper() + report.said()[1:] + ".") if report is not None else ""
    if failed:
        pid, why = failed
        before = [x.replace("_", " ") for x in made[:made.index(pid)]]
        reply = (f"I couldn't build the {pid.replace('_', ' ')}: {why.strip()}.\n\n"
                 + (f"The parts before it stay ({', '.join(before)}). " if before else "")
                 + "Build it again to retry it, change the plan, or carry on without it.")
    else:
        reply = (f"I built the plan's {len(made)} parts, in order:\n" + "\n".join(said)
                 + (f"\n\n{whole}" if whole else ""))
    steps["plan"] = f"{status}: {len(built)} of {len(made)} parts"
    store.append_log({"kind": "reply", "action": "plan", "ok": not failed, "reply": reply, "firstrun": True})
    emit("step", "Done", step="done")
    ok = not failed and (report is None or (report.all_pass and not report.waiting))
    return {"part": failed[0] if failed else (made[-1] if made else None), "ok": ok, "steps": steps,
            "reply": reply, "plan": status, "built": list(built)}
