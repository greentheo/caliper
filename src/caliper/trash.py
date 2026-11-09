"""CALI-105 (#98) — a part can be removed, and put back.

Nothing could remove a part: ``revert_part`` can't roll back a part's first version, and a second cone authored by
mistake would have stayed in the bar stool for good. Removing one moves its folder (script, versions, spec, history)
to the design's ``trash/``, with what named it (its assembly entry, the mates and rules on it, the grain said for its
panels, its place in the plan and the plan's rules on it), and takes it out of the design; restoring puts all of it
back. Never deleted outright. Out of the plan too (#153 review), or "Build it again" would author it anew.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from typing import Optional

from .design import DesignStore


def root(store: DesignStore) -> str:
    return os.path.join(store.root, "trash")


def listing(store: DesignStore) -> list[dict]:
    """What's in the design's trash, newest first: ``{id, part, removed}``."""
    out = []
    if os.path.isdir(root(store)):
        for tid in sorted(os.listdir(root(store)), reverse=True):
            meta = os.path.join(root(store), tid, "removed.json")
            if os.path.exists(meta):
                with open(meta) as f:
                    got = json.load(f)
                out.append({"id": tid, "part": got["part"]["id"], "removed": got["removed"]})
    return out


def _names_it(expr: str, pid: str) -> bool:
    from .assembly import _names

    try:
        return pid in _names(expr or "")
    except Exception:  # noqa: BLE001 — a rule that won't parse names nothing
        return False


def _out_of_plan(store: DesignStore, pid: str) -> Optional[dict]:
    """Take a part out of the design's plan, and what the plan says about it; what comes back on restore."""
    plan = store.design.plan
    parts = (plan or {}).get("parts") or []
    at = next((i for i, p in enumerate(parts) if p.get("id") == pid), None)
    if at is None:
        return None
    every = plan.get("rules") or []
    rules = [{"at": i, "rule": r} for i, r in enumerate(every) if _names_it(r.get("expr"), pid)]
    mounted = [p["id"] for p in parts if pid in (p.get("mounts_on") or [])]
    gone = {x["at"] for x in rules}
    store.design.plan = {**plan, "rules": [r for i, r in enumerate(every) if i not in gone],
                         "parts": [{**p, "mounts_on": [m for m in p["mounts_on"] if m != pid]} if p.get("mounts_on")
                                   else p for i, p in enumerate(parts) if i != at]}
    return {"part": parts[at], "index": at, "rules": rules, "mounted": mounted}


def _into_plan(store: DesignStore, was: dict) -> None:
    plan = store.design.plan
    if not plan:
        return
    pid = was["part"]["id"]
    parts = [{**p, "mounts_on": [*(p.get("mounts_on") or []), pid]} if p.get("id") in was["mounted"] else p
             for p in plan.get("parts") or [] if p.get("id") != pid]
    parts.insert(min(was["index"], len(parts)), was["part"])
    rules = list(plan.get("rules") or [])
    have = {r.get("id") for r in rules}
    for x in sorted(was["rules"], key=lambda x: x["at"]):      # each back where it was
        if x["rule"].get("id") not in have:
            rules.insert(min(x["at"], len(rules)), x["rule"])
    store.design.plan = {**plan, "parts": parts, "rules": rules}


def remove(store: DesignStore, pid: str) -> dict:
    """Take a part out of the design and its plan, its files to the trash. Returns ``{id, part, mates, rules}``: what
    went with it, by id."""
    from .design import _invalidate_build_cache

    entry = store.design.part(pid)
    if entry is None:
        raise ValueError(f"there's no part {pid!r}")
    tid = f"{pid}-{time.strftime('%Y%m%d-%H%M%S')}"
    while os.path.exists(os.path.join(root(store), tid)):
        tid += "x"
    here = os.path.join(root(store), tid)
    os.makedirs(here)
    _invalidate_build_cache(store.script_path(pid))
    if os.path.isdir(store.part_dir(pid)):
        shutil.move(store.part_dir(pid), os.path.join(here, "part"))
    asm = store.assembly
    mates = [m for m in asm.mates if pid in m.between]
    rules = [a for a in asm.assertions if _names_it(a.expr, pid)]
    planned = _out_of_plan(store, pid)
    meta = {"part": entry.model_dump(), "removed": time.time(),
            "assembly": next((p.model_dump() for p in asm.parts if p.id == pid), None),
            "mates": [m.model_dump() for m in mates], "rules": [a.model_dump(by_alias=True) for a in rules],
            "grain": (store.design.grain or {}).get(pid) if hasattr(store.design, "grain") else None,
            "plan": planned}
    with open(os.path.join(here, "removed.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str)
    store.design.parts = [p for p in store.design.parts if p.id != pid]
    asm.parts = [p for p in asm.parts if p.id != pid]
    asm.mates = [m for m in asm.mates if m not in mates]
    asm.assertions = [a for a in asm.assertions if a not in rules]
    if getattr(store.design, "grain", None):
        store.design.grain = {k: v for k, v in store.design.grain.items() if k != pid}
    store.save()
    store.append_log({"kind": "trash", "action": "removed", "part": pid, "id": tid})
    named = [a.id for a in rules] + [x["rule"]["id"] for x in (planned or {}).get("rules") or []
                                     if x["rule"]["id"] not in {a.id for a in rules}]
    return {"id": tid, "part": pid, "mates": [m.id for m in mates], "rules": named}


def restore(store: DesignStore, tid: Optional[str] = None, pid: Optional[str] = None) -> dict:
    """Put a removed part back, as it was (its files, its assembly entry, its mates and rules). By the trash's id, or
    the newest removal of that part."""
    from .assembly import Assertion, Mate, Part
    from .design import DesignPart

    if tid is None:
        tid = next((t["id"] for t in listing(store) if t["part"] == pid), None)
        if tid is None:
            raise ValueError(f"there's no {pid!r} in the design's trash")
    here = os.path.join(root(store), tid)
    with open(os.path.join(here, "removed.json")) as f:
        meta = json.load(f)
    pid = meta["part"]["id"]
    if store.design.part(pid) is not None or os.path.exists(store.part_dir(pid)):    # never over a part of that name
        raise ValueError(f"the design already has a part {pid!r}: rename or remove it first")
    if os.path.isdir(os.path.join(here, "part")):
        shutil.move(os.path.join(here, "part"), store.part_dir(pid))
    store.design.parts.append(DesignPart.model_validate(meta["part"]))
    asm = store.assembly
    if meta.get("assembly"):
        asm.parts.append(Part.model_validate(meta["assembly"]))
    ids = {p.id for p in asm.parts}
    back = [Mate.model_validate(m) for m in meta.get("mates") or [] if all(x in ids for x in m["between"])]
    asm.mates += back
    asm.assertions += [Assertion.model_validate(a) for a in meta.get("rules") or []]
    if meta.get("grain") and hasattr(store.design, "grain"):
        store.design.grain = {**(store.design.grain or {}), pid: meta["grain"]}
    if meta.get("plan"):
        _into_plan(store, meta["plan"])
    store.save()
    shutil.rmtree(here, ignore_errors=True)
    store.append_log({"kind": "trash", "action": "restored", "part": pid, "id": tid})
    return {"id": tid, "part": pid, "mates": [m.id for m in back]}
