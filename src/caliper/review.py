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

#: "a mirror of side_left", "mirrors side_left", "a mirror image of the left side": a pair the plan calls mirrored
_MIRROR_WORDS = re.compile(r"\bmirror(?:s|ed)?\b(?:(?:\s+image)?(?:\s+of)?\s+(?:the\s+)?([a-z_ ]+))?", re.I)
_EXCEPTION = re.compile(r"^\s*\w+(?:Error|Exception):\s*")


def _name(pid: str) -> str:
    return pid.replace("_", " ")


def _plain(detail: str) -> str:
    """An error's words without its class's name ("ValueError: doesn't go into it" is "doesn't go into it")."""
    return _EXCEPTION.sub("", detail or "") or "no reason given"


def _plan_parts(store: DesignStore) -> list[dict]:
    return list((store.design.plan or {}).get("parts") or [])


def _built(store: DesignStore, pid: str) -> bool:
    entry = store.design.part(pid)
    return bool(entry and entry.version and store.is_scripted(pid))


def _fit_fix(said: str, inner: str, host: str, c: float) -> str:
    """The change a fit finding proposes, by what failed (#247 review): off the slot, move it; play or too big, size the
    pocket."""
    if "doesn't sit in" in said:
        return f"Move the {_name(inner)} down into {host}'s slot."
    return f"Size {host}'s pocket to the {_name(inner)}: {c:g} mm a side."


def _rule_findings(store: DesignStore, report) -> dict:
    """The design's checks, as measured: a mate or a rule of the plan's that fails is a finding; one that couldn't be
    measured is said apart, never as measured (#247 review, rule 6)."""
    from .assembly import _names

    out = {"findings": [], "measured": 0, "unmeasured": [], "notes": []}
    if report is None:
        return out
    ids = {p.id for p in store.design.parts}
    mates = {m.id: m for m in store.assembly.mates}
    whys = {r.get("id"): r.get("why") for r in (store.design.plan or {}).get("rules") or []}
    for r in report.results:
        mate = mates.get(r.id)
        if r.status == "error":
            what = (f"whether the {_name(mate.between[0])} fits {mate.between[1]}'s pocket" if mate is not None and mate.kind == "fits_in"
                    else f"the plan's check {r.id}")
            out["unmeasured"].append(f"couldn't measure {what}: {_plain(r.detail)}")   # never as measured (#247)
            continue
        if r.status not in ("pass", "fail"):
            continue
        out["measured"] += 1
        if r.status == "pass":
            continue
        parts = list(mate.between) if mate else sorted(_names(r.expr) & ids)
        if mate is not None and mate.kind == "fits_in":
            inner, host = mate.between
            c = 0.3 if mate.value is None else abs(mate.value)
            said = r.detail or f"the {_name(inner)} doesn't fit {host}'s pocket"
            fix = _fit_fix(said, inner, host, c)
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
            why = whys.get(r.id)
            said = (f"the plan's check that {why} fails" if why else f"the plan's check {r.id} fails ({r.expr})") + (
                f": it measures {r.actual:.3g}" if isinstance(r.actual, (int, float)) else "")
            fix = "Change the parts it names so it passes, or the plan if the check is wrong."
        out["findings"].append({"kind": "rule", "id": r.id, "parts": parts, "said": said, "fix": fix, "measured": True})
    return out


def _pairs(store: DesignStore) -> list[tuple[str, str]]:
    """Every pair of parts the plan mounts on each other or says touch, built, each once."""
    seen, out = set(), []
    pairs = [(p["id"], m) for p in _plan_parts(store) for m in p.get("mounts_on") or []]
    pairs += [tuple(m.between) for m in store.assembly.mates if m.kind == "touch"]
    for a, b in pairs:
        key = frozenset((a, b))
        if a != b and key not in seen and _built(store, a) and _built(store, b):
            seen.add(key)
            out.append((a, b))
    return out


def _fit_findings(store: DesignStore) -> dict:
    """A fit for every pair mounted on or touching each other that the plan has no ``fits_in`` for (#247 review: a plan
    written before #243 has none, and step-stool-4's pockets went unlooked at). Measured both ways: where one goes into
    the other, the fit is measured at the plan's clearance or 0.3 mm; where neither does, nothing is said; where it
    can't tell, it says so."""
    from . import measure

    out = {"findings": [], "measured": 0, "unmeasured": [], "notes": []}
    planned = {frozenset(m.between) for m in store.assembly.mates if m.kind == "fits_in"}
    for a, b in _pairs(store):
        if frozenset((a, b)) in planned:
            continue                               # the plan's own fit, measured with the rest
        unsure = None
        for inner, host in ((a, b), (b, a)):
            try:
                gi, gh = store.part_geometry(inner), store.part_geometry(host)
                got, slid = measure.pocket(gi, gh), None
                if not got["in"] and "doesn't go into it" in got["why"]:
                    got, slid = _slid_in(gi, gh)       # short of its pocket: measured at its mouth, and said
            except Exception as e:  # noqa: BLE001 — said apart, never as measured
                unsure = f"whether the {_name(inner)} fits {host}'s pocket ({_plain(str(e))})"
                continue
            sides = [g for g in (got.get("gaps") or {}).values() if g is not None]
            if not got["in"] or not sides:
                if got["why"] and "doesn't go into it" not in got["why"] and got["in"] is False:
                    unsure = f"whether the {_name(inner)} fits {host}'s pocket ({got['why']})"
                continue
            out["measured"] += 1
            unsure = None
            c = measure.POCKET_CLEARANCE_MM
            off = max(abs(g - c) if g >= 0 else measure.POCKET_TOL_MM + c - g for g in sides)
            if off > measure.POCKET_TOL_MM:
                said = measure.pocket_said(inner, host, got, c)
                if slid is not None and got.get("axis") and not measure.pocket(gi, gh)["in"]:   # measured at the mouth
                    where = (f"it stops {slid:.0f} mm short of going in" if slid >= 0.5 else "it ends flush with it, not in it")
                    said = said.replace(f"the {_name(inner)} ", f"the {_name(inner)}, measured at the pocket's mouth "
                                        f"({where}), ", 1)
                out["findings"].append({"kind": "fit", "parts": [inner, host], "said": said, "measured": True,
                                        "fix": _fit_fix(said, inner, host, c)})
            break
        if unsure:
            out["unmeasured"].append(unsure)
    return out


#: How far short of a pocket a part may stop and still be measured against it, slid in along its own line (mm).
SLIDE_MM = 60.0


def _slid_in(inner, host) -> tuple[dict, float]:
    """A part that lines up with a pocket in its host but stops short of it, or flush with its mouth (step-stool-4's
    stretcher ends at each side's inner face): the pocket measured at its mouth, 2 mm in, against the part's own section,
    as :func:`measure.pocket` measures one it's in. Only where the host has a hole the part's section fits across (a bolt
    hole under a side isn't a pocket for it). ``(pocket, how far short it stops)``; ``({"in": False, …}, 0)`` otherwise."""
    import numpy as np

    from . import measure, spatial

    nothing = ({"in": False, "gaps": {}, "why": "doesn't go into it"}, 0.0)
    a, b = inner.require_mesh(), host.require_mesh()
    alo, ahi = a.bounds
    blo, bhi = b.bounds
    apart = [max(blo[k] - ahi[k], alo[k] - bhi[k]) for k in range(3)]
    k = int(np.argmax(apart))
    across = [i for i in range(3) if i != k]
    lines_up = all(alo[i] >= blo[i] - 1e-6 and ahi[i] <= bhi[i] + 1e-6 for i in across)
    if apart[k] < -0.05 or apart[k] > SLIDE_MM or not lines_up:   # flush with its mouth counts (stool-4's ends sit there)
        return nothing
    toward = 1.0 if ahi[k] <= blo[k] + 0.05 else -1.0
    end = ahi[k] if toward > 0 else alo[k]
    reach = min(SLIDE_MM, float(bhi[k] - blo[k]))
    for depth in np.arange(1.0, reach + 1e-9, 1.0):      # in from the part's end until walls close round its line
        centre = (alo + ahi) / 2.0
        centre[k] = end + toward * depth
        if bool(spatial.contains(b, [centre])[0]):
            return nothing                               # solid on its line before any pocket: it only sits on it
        gaps: dict = {}
        for i in across:
            half = (ahi[i] - alo[i]) / 2.0
            for sign in (1.0, -1.0):
                d = np.zeros(3)
                d[i] = sign
                loc, _, _ = spatial.intersects_location(b, np.array([centre]), np.array([d]))
                ahead = [float((p[i] - centre[i]) * sign) for p in loc if (p[i] - centre[i]) * sign > 1e-9]
                gaps[("+" if sign > 0 else "-") + "xyz"[i]] = round(min(ahead) - half, 3) if ahead else None
        near = [g for g in gaps.values() if g is not None and g < 2 * max(ahi[i] - alo[i] for i in across)]
        if len(near) == 4:                               # a pocket round its line: its mouth
            probes = []
            for i in across:                             # a pocket it fits across, not a bolt hole
                for f in (-0.4, 0.4):
                    q = centre.copy()
                    q[i] += f * (ahi[i] - alo[i])
                    probes.append(q)
            if sum(bool(x) for x in spatial.contains(b, probes)) > 2:
                return nothing
            return {"in": True, "axis": "xyz"[k], "gaps": gaps, "why": ""}, float(depth - 1.0)
    return nothing



def mirrored_pairs(store: DesignStore) -> tuple[list[tuple[str, str]], list[str]]:
    """``(pairs, unpaired)``: ``(part, source)`` for each part the plan calls a mirror of another (its ``mirror_of``, or
    "mirror of side_left", "mirrors the left side" in what it says it is), and the parts whose words say mirror with no
    part named."""
    from .chat import named_part

    ids = [p["id"] for p in _plan_parts(store)]
    out, unpaired = [], []
    for p in _plan_parts(store):
        src = p.get("mirror_of")
        words = " ".join(str(p.get(k) or "") for k in ("what", "intent"))
        if not src:
            m = _MIRROR_WORDS.search(words)
            src = named_part(m.group(1), [i for i in ids if i != p["id"]]) if m and m.group(1) else None
            if m and src is None:
                unpaired.append(p["id"])
        if src and src in ids and src != p["id"]:
            out.append((p["id"], src))
    return out, unpaired


def _mirror_findings(store: DesignStore) -> dict:
    from . import measure, mirror

    out = {"findings": [], "measured": 0, "unmeasured": [], "notes": []}
    pairs, unpaired = mirrored_pairs(store)
    out["notes"] += [f"the plan says {pid} is a mirror, but not of which part: it isn't compared" for pid in unpaired]
    for pid, src in pairs:
        if not (_built(store, pid) and _built(store, src)) or mirror.source_of(store, pid) == src:
            continue                               # a generated mirror is one by construction (#239)
        try:
            off = measure.mirror_off(store.part_geometry(pid), store.part_geometry(src))
        except Exception as e:  # noqa: BLE001 — a pair that can't be compared is said apart, never passed
            out["unmeasured"].append(f"couldn't compare {pid} with {src}, which the plan says it mirrors: {_plain(str(e))}")
            continue
        out["measured"] += 1
        if off > measure.MIRROR_MM:              # mirrors() in mm, as a mirror check reads it (#246 review)
            out["findings"].append({"kind": "mirror", "parts": [pid, src], "measured": True,
                                    "said": f"the plan says {pid} mirrors {src}, but their surfaces are up to {off:.1f} mm apart",
                                    "fix": f"Make {pid} the mirror of {src}."})
    return out


def _shadow_findings(store: DesignStore) -> dict:
    from . import skeleton

    out = {"findings": [], "measured": 0, "unmeasured": [], "notes": []}
    if not store.design.skeleton:
        return out
    ids = [p["id"] for p in _plan_parts(store)]
    for p in _plan_parts(store):
        if not _built(store, p["id"]):
            continue
        out["measured"] += 1
        r = skeleton.shadows(p["id"], store.read_script(p["id"]), store.design.skeleton, ids)
        if r.status == "fail":
            out["findings"].append({"kind": "shadow", "parts": [p["id"]], "measured": True,
                                    "said": r.detail.split(". Use the plan's numbers")[0],
                                    "fix": "Read the plan's numbers by their names, never a copy of its own."})
    return out


#: A stated size the solid can be measured for by its name: its height is up, its length its longest side (#247).
_ALONG = {"height": lambda e: e[2], "length": lambda e: max(e)}


def _stated_findings(store: DesignStore) -> dict:
    """A number the person gave (#247 review): checked only where a plan rule or check reads it, since those are measured
    on the solid; a length or height named for a part is measured on it here; one a part only names in its PARAMS is a
    note, and one nothing names is a note too. Only the measured ones count."""
    from . import aero
    from . import plan as P
    from .assembly import _names
    from .skeleton import _subject

    out = {"findings": [], "measured": 0, "unmeasured": [], "notes": []}
    stated = [s for s in store.design.skeleton or [] if s.get("source") == "stated"]
    if not stated:
        return out
    ruled: set = set()
    for expr in [a.expr for a in store.assembly.assertions] + [r.get("expr") or "" for r in (store.design.plan or {}).get("rules") or []]:
        ruled |= _names(expr)
    named = {p.id: set((aero.read_params(store.read_script(p.id)) or {}).keys()) for p in store.design.parts if store.is_scripted(p.id)}
    inches = store.design.display_units == "in"
    for s in stated:
        sv = P.SkeletonValue.model_validate(s)
        said = f"you said {_name(s['name'])} is {P.number(sv, inches)}"
        if s["name"] in ruled:
            out["measured"] += 1                   # a rule reads it: measured with the design's checks
            continue
        subject, size = _subject(s["name"])
        along, want = _ALONG.get(size), P.mm(sv)
        if subject in named and along and want and _built(store, subject):
            try:
                got = float(along(store.part_geometry(subject).require_mesh().extents))
            except Exception as e:  # noqa: BLE001
                out["unmeasured"].append(f"couldn't measure the {_name(subject)}'s {size}: {_plain(str(e))}")
                continue
            out["measured"] += 1
            if abs(got - want) > max(1.0, 0.01 * want):
                out["findings"].append({"kind": "stated", "parts": [subject], "measured": True,
                                        "said": f"{said}, and the {_name(subject)} is {got:.0f} mm {'tall' if size == 'height' else 'long'}",
                                        "fix": f"Make the {_name(subject)} {P.number(sv, inches)} {'tall' if size == 'height' else 'long'}, "
                                               f"or say what it should be."})
            continue
        whose = [pid for pid, keys in named.items() if s["name"] in keys]
        out["notes"].append(f"{said}; {'the ' + _name(whose[0]) + ' names it, but ' if whose else ''}no check measures it")
    return out


def findings(store: DesignStore, report=None) -> dict:
    """What's measured wrong with the built design (no model call): ``{"findings", "checks", "unmeasured", "notes"}``.
    ``checks`` counts only what was measured; what couldn't be is said apart, and notes are never findings (#247 review,
    rule 6). Each finding has ``kind`` (rule, fit, mirror, shadow, stated), ``parts``, ``said``, ``fix``, ``measured``."""
    if report is None:
        from . import chat

        report, _ = chat._measure_design(store)
    got = {"findings": [], "checks": 0, "unmeasured": [], "notes": []}
    for part in (_rule_findings(store, report), _fit_findings(store), _mirror_findings(store), _shadow_findings(store),
                 _stated_findings(store)):
        got["findings"] += part["findings"]
        got["checks"] += part["measured"]
        got["unmeasured"] += part["unmeasured"]
        got["notes"] += part["notes"]
    return got


def said(rec: dict) -> str:
    """The list, as the build's reply says it: measured findings first, each with its parts and the change proposed; then
    what couldn't be measured, and notes. An empty list says how many checks ran and to look at it, never that it's
    right."""
    unmeasured, notes = rec.get("unmeasured") or [], rec.get("notes") or []
    of = f"{rec['checks']} of {rec['checks'] + len(unmeasured)} checks measured" if unmeasured else f"{rec['checks']} checks"
    if not rec["findings"]:
        lines = [f"Measured after the build: nothing found in {of}. That's what the checks see, not that it's right: "
                 "look at it."]
    else:
        lines = [f"Measured after the build: {len(rec['findings'])} thing{'s' if len(rec['findings']) != 1 else ''} to fix "
                 f"({of}; no model reading yet):"]
        for f in rec["findings"]:
            whose = f" ({', '.join(f['parts'])})" if f["parts"] else ""
            lines.append(f"- {f['said'][:1].upper()}{f['said'][1:]}{whose}. {f['fix']}")
    if unmeasured:
        lines.append("Not measured:")
        lines += [f"- {u[:1].upper()}{u[1:]}." for u in unmeasured]
    if notes:
        lines.append("Notes:")
        lines += [f"- {n[:1].upper()}{n[1:]}." for n in notes]
    return "\n".join(lines)
