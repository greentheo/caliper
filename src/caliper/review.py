"""CALI-160 (#238), slice A — after a plan's build, what's measured wrong, as a list, with no model call.

Theo, after step-stool-4: every part built on its first try, and still they didn't go together (the sides weren't
mirrors, neither pocket fit the stretcher, the stretcher missed the left side). All of it is visible once every part
exists, and none of it to a designer writing one part at a time. So after a plan's build, Caliper lists what it
**measured** wrong, each finding naming its parts, saying what's wrong in the person's words and the change it
proposes:

- a plan rule or mate that fails (a pocket's fit says its play: "the stretcher has 19.1 mm of play in side_left's
  pocket");
- a pair the plan calls mirrored whose surfaces are more than 0.2 mm apart, mirrored in place (``mirrors()``, #239);
- a part that sets its own copy of a size the plan shares (#240);
- a number the person stated that no part and no rule reads, so nothing measures it.

Nothing here is a model's reading (slice B adds those, marked as read). An empty list never says "it's right": it
says how many checks ran, and to look at it.
"""

from __future__ import annotations

import re
from typing import Optional

from .design import DesignStore

_MIRROR_WORDS = re.compile(r"\bmirror(?:\s+image)?\s+of\s+(?:the\s+)?(\w+)", re.I)


def _name(pid: str) -> str:
    return pid.replace("_", " ")


def _plan_parts(store: DesignStore) -> list[dict]:
    return list((store.design.plan or {}).get("parts") or [])


def _built(store: DesignStore, pid: str) -> bool:
    entry = store.design.part(pid)
    return bool(entry and entry.version and store.is_scripted(pid))


def _rule_findings(store: DesignStore, report) -> list[dict]:
    """The design's failing checks: a mate or a rule of the plan's, measured."""
    from .assembly import _names

    if report is None:
        return []
    ids = {p.id for p in store.design.parts}
    mates = {m.id: m for m in store.assembly.mates}
    out = []
    for r in report.results:
        if r.status not in ("fail", "error"):
            continue
        mate = mates.get(r.id)
        parts = list(mate.between) if mate else sorted(_names(r.expr) & ids)
        if mate is not None and mate.kind == "fits_in":
            inner, host = mate.between
            c = 0.3 if mate.value is None else abs(mate.value)
            said = r.detail or f"the {_name(inner)} doesn't fit {host}'s pocket"
            fix = f"Size {host}'s pocket to the {_name(inner)}: {c:g} mm a side."
        elif mate is not None and mate.kind == "touch":
            a, b = mate.between
            gap = r.actual if isinstance(r.actual, (int, float)) else None
            said = (f"the {_name(a)} doesn't meet {b}" + (f": {abs(gap):.1f} mm {'apart' if gap > 0 else 'into it'}"
                                                          if gap is not None else ""))
            fix = f"Move the {_name(a)} or {b} so they meet."
        elif mate is not None and mate.kind == "no_interference":
            a, b = mate.between
            said = f"the {_name(a)} runs into {b}" + (f" ({r.actual:.0f} mm³ of overlap)" if isinstance(r.actual, (int, float)) else "")
            fix = f"Move or trim the {_name(a)} or {b} so they don't overlap."
        else:
            said = f"the plan's check {r.id} fails ({r.expr}" + (f", it measures {r.actual:.3g}" if isinstance(r.actual, (int, float)) else "") + ")"
            if r.status == "error":
                said = f"the plan's check {r.id} couldn't be measured: {r.detail or 'no reason given'}"
            fix = "Change the parts it names so it passes, or the plan if the check is wrong."
        out.append({"kind": "rule", "id": r.id, "parts": parts, "said": said, "fix": fix, "measured": True})
    return out


def mirrored_pairs(store: DesignStore) -> list[tuple[str, str]]:
    """``(part, source)`` for each part the plan calls a mirror of another: its ``mirror_of``, or "mirror of side_left"
    in what it says it is."""
    ids = {p["id"] for p in _plan_parts(store)}
    out = []
    for p in _plan_parts(store):
        src = p.get("mirror_of")
        if not src:
            m = _MIRROR_WORDS.search(" ".join(str(p.get(k) or "") for k in ("what", "intent")))
            src = m.group(1) if m else None
        if src and src in ids and src != p["id"]:
            out.append((p["id"], src))
    return out


def _mirror_findings(store: DesignStore) -> tuple[list[dict], int]:
    from . import measure, mirror

    out, checked = [], 0
    for pid, src in mirrored_pairs(store):
        if not (_built(store, pid) and _built(store, src)) or mirror.source_of(store, pid) == src:
            continue                               # a generated mirror is one by construction (#239)
        checked += 1
        try:
            off = measure.mirror_off(store.part_geometry(pid), store.part_geometry(src))
        except Exception as e:  # noqa: BLE001 — a pair that can't be compared is said, never passed
            out.append({"kind": "mirror", "parts": [pid, src], "measured": True,
                        "said": f"the plan says {pid} mirrors {src}, and they couldn't be compared ({e})",
                        "fix": f"Make {pid} the mirror of {src}."})
            continue
        if off > measure.MIRROR_MM:              # mirrors() in mm, as a mirror check reads it (#246 review)
            out.append({"kind": "mirror", "parts": [pid, src], "measured": True,
                        "said": f"the plan says {pid} mirrors {src}, but their surfaces are up to {off:.1f} mm apart",
                        "fix": f"Make {pid} the mirror of {src}."})
    return out, checked


def _shadow_findings(store: DesignStore) -> tuple[list[dict], int]:
    from . import skeleton

    if not store.design.skeleton:
        return [], 0
    out, checked = [], 0
    for p in _plan_parts(store):
        if not _built(store, p["id"]):
            continue
        checked += 1
        r = skeleton.shadows(p["id"], store.read_script(p["id"]), store.design.skeleton)
        if r.status == "fail":
            out.append({"kind": "shadow", "parts": [p["id"]], "measured": True,
                        "said": r.detail.split(". Use the plan's numbers")[0],
                        "fix": "Read the plan's numbers by their names, never a copy of its own."})
    return out, checked


def _stated_findings(store: DesignStore) -> tuple[list[dict], int]:
    """A number the person gave that no built part's PARAMS and no check reads: nothing measures it."""
    from . import aero
    from . import plan as P
    from .assembly import _names

    stated = [s for s in store.design.skeleton or [] if s.get("source") == "stated"]
    if not stated:
        return [], 0
    read: set = set()
    for p in store.design.parts:
        if store.is_scripted(p.id):
            read |= set((aero.read_params(store.read_script(p.id)) or {}).keys())
    for expr in [a.expr for a in store.assembly.assertions] + [r.get("expr") or "" for r in (store.design.plan or {}).get("rules") or []]:
        read |= _names(expr)
    out = []
    for s in stated:
        if s["name"] not in read:
            sv = P.SkeletonValue.model_validate(s)
            out.append({"kind": "stated", "parts": [], "measured": True,
                        "said": f"you said {_name(s['name'])} is {P.number(sv, store.design.display_units == 'in')}, "
                                "and no part reads it, so nothing measures it",
                        "fix": f"Use {s['name']} in the parts it's about, or a check on it."})
    return out, len(stated)


def findings(store: DesignStore, report=None) -> dict:
    """What's measured wrong with the built design: ``{"findings": [...], "checks": n}``. Each finding has ``kind``
    (rule, mirror, shadow, stated), ``parts``, ``said``, ``fix`` and ``measured: True``. No model call."""
    if report is None:
        from . import chat

        report, _ = chat._measure_design(store)
    got = _rule_findings(store, report)
    checks = len(report.results) if report is not None else 0
    for find in (_mirror_findings, _shadow_findings, _stated_findings):
        more, n = find(store)
        got += more
        checks += n
    return {"findings": got, "checks": checks}


def said(rec: dict, inches: Optional[bool] = None) -> str:
    """The list, as the build's reply says it: measured findings first, each with its parts and the change proposed.
    An empty list says how many checks ran and to look at it, never that it's right."""
    if not rec["findings"]:
        return (f"Measured after the build: nothing found in {rec['checks']} checks. That's what the checks see, not "
                "that it's right: look at it.")
    lines = [f"Measured after the build: {len(rec['findings'])} thing{'s' if len(rec['findings']) != 1 else ''} to fix "
             f"(of {rec['checks']} checks; no model reading yet):"]
    for f in rec["findings"]:
        whose = f" ({', '.join(f['parts'])})" if f["parts"] else ""
        lines.append(f"- {f['said'][:1].upper()}{f['said'][1:]}{whose}. {f['fix']}")
    return "\n".join(lines)
