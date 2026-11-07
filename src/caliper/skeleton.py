"""CALI-35c (#3c) — the skeleton's numbers drive the parts.

#3a plans a design of several parts around a skeleton: the numbers they share, named ("mast_top_z: 7 ft"), with the
rules between parts written over them. #3b builds the parts with the skeleton in each designer's prompt. Here a part's
``PARAMS`` key that the skeleton names takes the skeleton's value when it's built (``assembly.skeleton_params``: its
geometry and what it declares, so its pieces and loads move with its shape). So "make the mast 10 ft" after the build
is one number: every part that reads it is written again as a new version (same script, no call to Claude), and the
whole design is measured again, every rule between the parts with it. A part that hard-codes a shared number instead
of reading it doesn't move, and the plan's rule pinning that interface fails: said, never hidden.
"""

from __future__ import annotations

from typing import Optional

from .design import DesignStore


def readers(store: DesignStore, names) -> list[str]:
    """The built, scripted parts whose ``PARAMS`` read one of these skeleton names, in the design's order."""
    from .aero import read_params

    names = set(names)
    out = []
    for p in store.design.parts:
        if not p.version or not store.is_scripted(p.id):
            continue
        if names & set(read_params(store.read_script(p.id)) or {}):
            out.append(p.id)
    return out


def drive(store: DesignStore, skeleton: list, said: str = "") -> dict:
    """Set the skeleton to ``skeleton`` (each ``{name, value, unit, …}``), rebuild every part that reads a number that
    changed, and measure the whole design again. Returns ``{changed: {name: (before, after)}, rebuilt: [ids],
    failed: {id: why}, report}``: no authoring call is made."""
    from . import plan as P

    before = {s["name"]: s for s in (store.design.skeleton or [])}
    after = {(s if isinstance(s, dict) else s.model_dump())["name"]: (s if isinstance(s, dict) else s.model_dump())
             for s in skeleton}
    unknown = sorted(set(after) - set(before))
    if unknown:
        raise ValueError(f"the skeleton has no {', '.join(unknown)}: a new shared number is a change to the plan")
    changed = {n: (before[n]["value"], after[n]["value"]) for n in after
               if (before[n]["value"], before[n]["unit"]) != (after[n]["value"], after[n]["unit"])}
    if not changed:
        return {"changed": {}, "rebuilt": [], "failed": {}, "report": None}
    store.design.skeleton = [after.get(n, s) for n, s in before.items()]
    store.save()
    note = said or "; ".join(f"{n} {a:g} → {b:g}" for n, (a, b) in changed.items())
    rebuilt, failed = [], {}
    for pid in readers(store, changed):
        try:
            store.part_geometry(pid)                 # builds with the new numbers: it raises if it won't
        except Exception as e:  # noqa: BLE001 — a part the new number breaks is named, the rest still rebuild
            failed[pid] = str(e)
            continue
        # a new version, the same script: its strength check, weight and score are of the old shape now
        store.write_part(pid, store.read_script(pid), action="skeleton", feedback=note,
                         extra={"skeleton": {n: list(v) for n, v in changed.items()}})
        rebuilt.append(pid)
    report, errors = store.evaluate(tolerant=True)
    failed.update({k: v for k, v in (errors or {}).items() if k not in failed})
    return {"changed": changed, "rebuilt": rebuilt, "failed": failed, "report": report,
            "units": {n: after[n]["unit"] for n in changed}, "values": P.skeleton_values(store.design.skeleton)}


def said(result: dict) -> str:
    """The chat's reply for a drive: what changed, what rebuilt, and what the design's checks say now."""
    ch = result["changed"]
    if not ch:
        return "That didn't change a shared number."
    units = result.get("units") or {}
    lines = ["Changed " + "; ".join(f"{n.replace('_', ' ')} from {a:g} to {b:g} {units.get(n, '')}".rstrip()
                                    for n, (a, b) in ch.items()) + "."]
    if result["rebuilt"]:
        lines.append("Rebuilt from it, with no new design: the " + ", the ".join(x.replace("_", " ")
                                                                                 for x in result["rebuilt"]) + ".")
    else:
        lines.append("No part reads it: nothing rebuilt.")
    for pid, why in result["failed"].items():
        lines.append(f"✗ The {pid.replace('_', ' ')} won't build with it: {why}")
    rep = result.get("report")
    if rep is not None:
        lines.append(f"The design checks: {rep.said()}.")
    return "\n\n".join(lines)
