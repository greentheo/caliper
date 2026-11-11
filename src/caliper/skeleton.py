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
    builds: dict = {}
    for pid, script in scripts.items():             # every part built with its new numbers first
        if pid in out["refused"]:
            continue
        built = builds[pid] = sandbox.run_script(script, {})
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
                         extra={"skeleton": {n: list(changed[n]) for n in names}, **({"asked": said} if said else {})},
                         built=(scripts[pid], {}, builds[pid].geometry) if builds.get(pid) else None)
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


# ---------------------------------------------------------------------------
# CALI-162 (#240) — a part reads a shared size, it never restates it
# ---------------------------------------------------------------------------
#: A size's last word, as a PARAMS name ends: stretcher_w and stretcher_width are both its width.
SIZES = {"w": "width", "wid": "width", "width": "width", "wide": "width", "h": "height", "ht": "height",
         "height": "height", "tall": "height", "t": "thickness", "th": "thickness", "thk": "thickness",
         "thick": "thickness", "thickness": "thickness", "d": "depth", "depth": "depth", "deep": "depth",
         "l": "length", "len": "length", "length": "length", "long": "length", "dia": "diameter", "diam": "diameter",
         "diameter": "diameter", "r": "radius", "rad": "radius", "radius": "radius", "gap": "clearance",
         "clear": "clearance", "clearance": "clearance", "spacing": "spacing", "pitch": "spacing"}
#: How close a part's own number may be to the plan's and still be it (mm, or the same number in inches).
SAME_MM = 0.05
SHADOW = "skeleton_shadow"


def _subject(name: str) -> tuple[str, str]:
    """``("stretcher", "thickness")`` for stretcher_t; ``("", "")`` where the name doesn't end in a size."""
    tokens = [t for t in name.lower().split("_") if t]
    if len(tokens) < 2 or tokens[-1] not in SIZES:
        return "", ""
    return "_".join(tokens[:-1]), SIZES[tokens[-1]]


def _agrees(v: float, mm: float) -> bool:
    return abs(v - mm) <= SAME_MM or abs(v * 25.4 - mm) <= SAME_MM


def shadows(pid: str, script: str, skeleton: list):
    """Whether part ``pid``'s script reads the plan's shared sizes rather than setting its own (CALI-162, #240: both
    sides of step-stool-4 set ``stretcher_w`` 38.1 mm and ``stretcher_h`` 88.9 mm, a 2×4, while the stretcher was 19 ×
    101.6 mm). A ``PARAMS`` key with a skeleton's name and another value, or a near-name (same subject, a size word:
    ``stretcher_w`` beside ``stretcher_thickness``), fails: "side_left sets its own stretcher thickness: 38.1 mm
    against the plan's 19 mm". One :class:`AssertionResult`, ``skeleton_shadow``; a pass where none does."""
    from . import aero
    from . import plan as P
    from .evaluate import AssertionResult

    expr = "the part reads the plan's shared sizes by their names"
    params = aero.read_params(script or "") or {}
    plan: dict = {}
    for s in skeleton or []:
        sv = s if isinstance(s, P.SkeletonValue) else P.SkeletonValue.model_validate(s)
        plan[sv.name] = P.mm(sv) if P.mm(sv) is not None else float(sv.value)
    said = []
    for key, v in params.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if key in plan:
            if not _agrees(float(v), plan[key]):
                said.append(f"{pid} sets its own {key.replace('_', ' ')}: {v:g} mm against the plan's {plan[key]:g} mm")
            continue
        subject, size = _subject(key)
        same = [n for n in plan if subject and _subject(n)[0] == subject]
        if not same:
            continue
        name = next((n for n in same if _subject(n)[1] == size), None) or min(same, key=lambda n: abs(plan[n] - v))
        words = name.replace("_", " ")
        said.append(f"{pid} sets its own {words}: {v:g} mm against the plan's {plan[name]:g} mm" if not _agrees(float(v), plan[name])
                    else f"{pid} restates the plan's {words} as {key}: read {name} instead")
    if not said:
        return AssertionResult(SHADOW, expr, "pass", True, actual=0)
    names = sorted({n for n in plan})
    return AssertionResult(SHADOW, expr, "fail", False, actual=len(said),
                           detail="; ".join(said) + f". Use the plan's numbers by their names in PARAMS ({', '.join(names)}), "
                                  "never your own: a size two parts share is the plan's.")
