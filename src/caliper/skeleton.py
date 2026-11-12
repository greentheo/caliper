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
    from . import aero, load_study, mirror, sandbox

    before = {s["name"]: s for s in (store.design.skeleton or [])}
    after = {(s if isinstance(s, dict) else s.model_dump())["name"]: (s if isinstance(s, dict) else s.model_dump())
             for s in skeleton}
    unknown = sorted(set(after) - set(before))
    if unknown:
        raise ValueError(f"the skeleton has no {', '.join(unknown)}: a new shared number is a change to the plan")
    changed = {n: (before[n]["value"], after[n]["value"]) for n in after
               if (before[n]["value"], before[n]["unit"]) != (after[n]["value"], after[n]["unit"])}
    out = {"changed": changed, "rebuilt": {}, "unmoved": {}, "refused": {}, "strength": [], "report": None,
           "follows": {}, "units": {n: after[n]["unit"] for n in changed}}
    if not changed:
        return out
    # what each reading part's script becomes, before anything is saved
    scripts: dict[str, str] = {}
    for n in changed:
        old_mm, new_mm = _mm(before[n]), _mm(after[n])
        for pid in readers(store, n):
            source = mirror.source_of(store, pid)
            if source:                             # a mirror is never written: its source is, and it follows (#246)
                out["follows"][pid] = source
                pid = source
            if n in out["rebuilt"].get(pid, []):
                continue
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
    for pid, script in scripts.items():             # every write checked before any is made (#246): a refusal changes nothing
        if pid not in out["refused"] and mirror.of(script):
            out["refused"][pid] = mirror.said(pid, mirror.of(script)["source"])
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


def said_name(name: str) -> str:
    """A number's name in words, by its size word: floor_t is "the floor thickness", stretcher_w "the stretcher width"."""
    subject, size = _subject(name)
    return f"{subject.replace('_', ' ')} {size}" if subject else name.replace("_", " ")


def shadows(pid: str, script: str, skeleton: list, parts: Optional[list] = None):
    """Whether part ``pid``'s script reads the plan's shared sizes rather than setting its own (CALI-162, #240).

    A part's number is compared only with a plan **size** of the same subject and the same size word (#243 review:
    by closest value, ``flange_t`` was taken for the flange width and ``stretcher_len`` for the stretcher's height;
    by the word alone, a part's board height ``stretcher_h`` was taken for the plan's ``stretcher_height``, which is
    where the stretcher sits). So:

    - the plan's own name with another value fails: "side_left sets its own ply thickness: 25 mm against the plan's
      19.05 mm"; so does ``stretcher_thickness`` against the plan's ``stretcher_t``;
    - the same value under another name is a note, not a fail ("restates the plan's ply thickness as ply_t");
    - a size of another part the plan doesn't name is a note ("the plan doesn't name the stretcher width: side_left
      sets 19 mm");
    - a part's own sizes (``top_t`` on the top), positions, counts and loads are never compared with a size.

    One :class:`AssertionResult`, ``skeleton_shadow``: fail on a mismatch, else pass, with any notes as its detail."""
    from . import aero
    from . import plan as P
    from .evaluate import AssertionResult

    expr = "the part reads the plan's shared sizes by their names"
    params = aero.read_params(script or "") or {}
    plan: dict = {}
    for s in skeleton or []:
        sv = s if isinstance(s, P.SkeletonValue) else P.SkeletonValue.model_validate(s)
        plan[sv.name] = (P.mm(sv) if P.mm(sv) is not None else float(sv.value), P.kind_of(sv))
    own = {pid, *pid.split("_")}
    others = set(parts or []) - {pid}
    wrong, notes = [], []
    for key, v in params.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if key in plan:                                # its own name: the same number, whatever kind it is
            value, kind = plan[key]
            if not _agrees(float(v), value):
                unit = " mm" if kind in ("size", "position", "unclear") else ""
                (notes if kind == "unclear" else wrong).append(
                    f"the plan's {said_name(key)} may be where something sits: {pid} sets {v:g}{unit}, the plan {value:g}{unit}"
                    if kind == "unclear" else f"{pid} sets its own {said_name(key)}: {v:g}{unit} against the plan's {value:g}{unit}")
            continue
        subject, size = _subject(key)
        if not subject:
            continue
        same = [n for n, (_, kind) in plan.items() if kind in ("size", "unclear") and _subject(n) == (subject, size)]
        if same:                                       # even a part's own size, where the plan shares it (#243 re-check)
            name = same[0]
            if _agrees(float(v), plan[name][0]):
                notes.append(f"{pid} restates the plan's {said_name(name)} as {key}: read {name} instead")
            elif plan[name][1] == "unclear":
                notes.append(f"the plan's {said_name(name)} may be where something sits: {pid} sets {v:g} mm, the plan "
                             f"{plan[name][0]:g} mm")
            else:
                wrong.append(f"{pid} sets its own {said_name(name)}: {v:g} mm against the plan's {plan[name][0]:g} mm")
        elif subject in own:                           # a part's own size the plan doesn't share is its own
            continue
        elif subject in others:                        # another part's size, which the plan doesn't share
            notes.append(f"the plan doesn't name the {said_name(key)}: {pid} sets it at {v:g} mm")
    if not wrong:
        return AssertionResult(SHADOW, expr, "pass", True, actual=0, detail="; ".join(notes))
    return AssertionResult(SHADOW, expr, "fail", False, actual=len(wrong),
                           detail="; ".join(wrong) + ". Use the plan's numbers by their names in PARAMS, never your "
                                  "own: a size two parts share is the plan's." + (f" (Also: {'; '.join(notes)}.)" if notes else ""))


#: The size words a part's section is said by, in the skeleton: its thickness and its height (#240).
SECTION = ("thickness", "height")
#: How much of its own box a part must fill to be read as a board, whose section is its two smaller sides (#243).
BOARD_FILL = 0.9


def known_section(skeleton: list, pid: str) -> dict:
    """``{"thickness": name, "height": name}``: the sizes of part ``pid``'s section the skeleton names as sizes."""
    from . import plan as P

    out = {}
    for s in skeleton or []:
        sv = s if isinstance(s, P.SkeletonValue) else P.SkeletonValue.model_validate(s)
        subject, size = _subject(sv.name)
        if subject == pid and size in SECTION and P.kind_of(sv) == "size":
            out.setdefault(size, sv.name)
    return out


def _section_name(skeleton: list, pid: str, word: str) -> str:
    """The name a measured size goes under: ``{pid}_{word}``, or ``{pid}_t`` / ``{pid}_h`` where the plan's name is
    something else already (step-stool-4's ``stretcher_height`` is where it sits)."""
    full = f"{pid}_{word}"
    taken = next((s for s in skeleton or [] if s.get("name") == full), None)
    return full if taken is None or taken.get("source") == "measured" else f"{pid}_{word[0]}"


def section(store, pid: str, geometry) -> list[dict]:
    """Part ``pid``'s section as built, into the skeleton: whichever of its thickness and height (its two smaller
    sizes) the plan doesn't already name as a size, source ``measured``, ``of`` the part (CALI-162, #240). Only for a
    board, square to the axes and filling its box (#243 review: an L of 3 mm angle read as 50 mm thick); otherwise
    any size measured off it before is dropped, said in its history, and []. Written again in place when measured
    again."""
    from .measure import _square

    m = geometry.require_mesh()
    box = float(m.bounding_box.volume)
    if box <= 0 or float(abs(m.volume)) < BOARD_FILL * box or not _square(m):
        old = [s for s in store.design.skeleton or [] if s.get("source") == "measured" and s.get("of") == pid]
        if old:                                    # not a board now: its last measure would go stale (#243 re-check)
            store.design.skeleton = [s for s in store.design.skeleton if s not in old]
            store.save()
            if store.design.part(pid):
                store.append_history(pid, {"kind": "note", "said": "its measured section is dropped: it isn't a plain "
                                           "board now (" + ", ".join(s["name"] for s in old) + ")"})
        return []
    lo, hi = m.bounds
    dims = dict(zip(SECTION, sorted(float(b - a) for a, b in zip(lo, hi))[:2]))
    planned = known_section([s for s in store.design.skeleton or [] if s.get("source") != "measured"], pid)
    got = [{"name": _section_name(store.design.skeleton, pid, word), "value": round(v, 2), "unit": "mm",
            "why": f"the {pid.replace('_', ' ')}'s {word} as built", "source": "measured", "kind": "size", "of": pid}
           for word, v in dims.items() if word not in planned]
    by = {g["name"]: g for g in got}
    kept = [by.pop(s.get("name")) if s.get("name") in by and s.get("source") == "measured" else s
            for s in store.design.skeleton or []]
    names = {s.get("name") for s in kept}
    store.design.skeleton = kept + [g for g in by.values() if g["name"] not in names]
    store.save()
    return got


def remeasure(store, pid: str) -> list[dict]:
    """A measured section of ``pid`` in the skeleton, measured again now it's changed (#243 review: never stale)."""
    if not any(s.get("source") == "measured" and s.get("of") == pid for s in store.design.skeleton or []):
        return []
    try:
        return section(store, pid, store.part_geometry(pid))
    except Exception:  # noqa: BLE001 — a part that won't build keeps its last measure; its build says why
        return []
