"""CALI-35c (#3c) — the skeleton's numbers drive the parts.

#3a plans a design of several parts around a skeleton: the numbers they share, named ("mast_top_z: 7 ft"), with the
rules between parts written over them. #3b builds the parts with the skeleton in each designer's prompt. Here, changing
a skeleton number after the build ("make the mast 10 ft") writes it into every part that reads it: that part's
``PARAMS`` value is rewritten in its script (``aero.set_params``, the same rewrite a by-hand edit makes, #147) and saved
as a new version ("mast_top_z set to 3048 mm by the skeleton"). Builds always use a script's own ``PARAMS``: nothing
changes shape at the same version, and its older runs read as older (#143 review, the foreman's call).

- **Who reads a number:** a part reads it where the plan's rules name both (``abs(bbox(mast).max_z - mast_top_z)``):
  never by a ``PARAMS`` key that only happens to share the name. A part the plan says reads it but whose ``PARAMS``
  hasn't got it (it hard-codes it) doesn't move: said, and the rule pinning it fails.
- **Inches:** a part whose own default is the skeleton's old value in inches (84 for 2133.6 mm) is refused, with why:
  writing mm into it would make it 25.4 times off. An mm script's default is the skeleton's own number: it can't trip.
- **All or nothing:** every part is built with its new numbers before anything is saved; if one is refused or won't
  build, nothing changes (the skeleton, and every part's version), and the reply says which part and why.
"""

from __future__ import annotations

from typing import Optional

from .design import DesignStore


def _rules(store: DesignStore) -> list[str]:
    plan = [r.get("expr") or "" for r in (store.design.plan or {}).get("rules") or []]
    return plan + [a.expr for a in store.assembly.assertions]


def readers(store: DesignStore, name: str) -> list[str]:
    """The built, scripted parts the plan's rules say read this skeleton number: a rule names both."""
    from .assembly import _names

    named: set = set()
    for expr in _rules(store):
        try:
            names = _names(expr)
        except Exception:  # noqa: BLE001 — a rule that won't parse names nothing
            continue
        if name in names:
            named |= names
    return [p.id for p in store.design.parts if p.id in named and p.version and store.is_scripted(p.id)]


def _mm(entry: dict) -> Optional[float]:
    from . import plan as P

    sv = P.SkeletonValue.model_validate(entry)
    got = P.mm(sv)
    return got if got is not None else float(sv.value)


def drive(store: DesignStore, skeleton: list, said: str = "") -> dict:
    """Set the skeleton to ``skeleton`` (each ``{name, value, unit, …}``) and write each changed number into every part
    the plan says reads it, as a new version; then measure the whole design again. All or nothing. Returns
    ``{changed, rebuilt: {pid: [names]}, unmoved: {pid: why}, refused: {pid: why}, strength: [pids], report}``; no
    authoring call is made."""
    from . import aero, load_study, sandbox

    before = {s["name"]: s for s in (store.design.skeleton or [])}
    after = {(s if isinstance(s, dict) else s.model_dump())["name"]: (s if isinstance(s, dict) else s.model_dump())
             for s in skeleton}
    unknown = sorted(set(after) - set(before))
    if unknown:
        raise ValueError(f"the skeleton has no {', '.join(unknown)}: a new shared number is a change to the plan")
    changed = {n: (before[n]["value"], after[n]["value"]) for n in after
               if (before[n]["value"], before[n]["unit"]) != (after[n]["value"], after[n]["unit"])}
    out = {"changed": changed, "rebuilt": {}, "unmoved": {}, "refused": {}, "strength": [], "report": None,
           "units": {n: after[n]["unit"] for n in changed}}
    if not changed:
        return out
    # what each reading part's script becomes, before anything is saved
    scripts: dict[str, str] = {}
    for n in changed:
        old_mm, new_mm = _mm(before[n]), _mm(after[n])
        for pid in readers(store, n):
            script = scripts.get(pid) or store.read_script(pid)
            own = aero.read_params(script) or {}
            if n not in own:
                out["unmoved"][pid] = (f"the plan's rules read {n} on it, but its PARAMS has no {n}: it doesn't move "
                                       f"with it")
                continue
            d = float(own[n])
            if old_mm and abs(d * 25.4 - old_mm) <= 0.02 * abs(old_mm) < abs(d - old_mm):
                out["refused"][pid] = (f"its PARAMS has {n} = {d:g}, the skeleton's {old_mm:g} mm in inches: write it "
                                       f"in mm, or setting it would make it 25.4 times off")
                continue
            scripts[pid] = aero.set_params(script, {n: new_mm})
            out["rebuilt"].setdefault(pid, []).append(n)
    for pid, script in scripts.items():             # every part built with its new numbers first
        if pid in out["refused"]:
            continue
        built = sandbox.run_script(script, {})
        if not built.ok:
            tail = [ln for ln in (built.feedback or "").strip().splitlines() if ln.strip()]
            out["refused"][pid] = f"it won't build with it: {tail[-1].strip() if tail else 'the build failed'}"
    if out["refused"]:                              # all or nothing: the skeleton and every part as they were
        out["rebuilt"] = {}
        return out
    store.design.skeleton = [after.get(n, s) for n, s in before.items()]
    store.save()
    for pid, names in out["rebuilt"].items():
        said_n = "; ".join(f"{n} set to {after[n]['value']:g} {after[n]['unit']}"
                           + (f" ({_mm(after[n]):g} mm)" if after[n]["unit"] != "mm" else "") for n in names)
        store.write_part(pid, scripts[pid], action="skeleton", feedback=said_n + " by the skeleton",
                         extra={"skeleton": {n: list(changed[n]) for n in names}, **({"asked": said} if said else {})})
        if load_study.list_runs(store, pid):
            out["strength"].append(pid)              # its strength check is of the older shape now
    out["report"], errors = store.evaluate(tolerant=True)
    out["failed"] = errors or {}
    return out


def _part(pid: str) -> str:
    return "the " + pid.replace("_", " ")


def said(result: dict) -> str:
    """The chat's reply for a drive: what changed, what rebuilt and the key it set, what didn't, what to check again,
    and what the design's checks say now."""
    ch = result["changed"]
    if not ch:
        return "That didn't change a shared number."
    units = result.get("units") or {}
    nums = "; ".join(f"{n.replace('_', ' ')} from {a:g} to {b:g} {units.get(n, '')}".rstrip() for n, (a, b) in ch.items())
    if result.get("refused"):
        return ("Nothing changed: " + "; ".join(f"{_part(p)} can't take it: {why}" for p, why in result["refused"].items())
                + f". The skeleton and every part are as they were ({nums} not made).")
    lines = [f"Changed {nums}."]
    if result["rebuilt"]:
        lines.append("Rebuilt from it, with no new design: " + ", ".join(
            f"{_part(p)} ({', '.join(ns)})" for p, ns in result["rebuilt"].items()) + ".")
    else:
        lines.append("No part reads it: nothing rebuilt.")
    for pid, why in result.get("unmoved", {}).items():
        lines.append(f"! {_part(pid)[:1].upper() + _part(pid)[1:]}: {why}.")
    for pid, why in (result.get("failed") or {}).items():
        lines.append(f"✗ {_part(pid)[:1].upper() + _part(pid)[1:]} won't build now: {why}")
    if result.get("strength"):
        lines.append("Strength: check it again on " + " and ".join(_part(p) for p in result["strength"]) + ".")
    rep = result.get("report")
    if rep is not None:
        lines.append(f"The design checks: {rep.said()}.")
    return "\n\n".join(lines)
