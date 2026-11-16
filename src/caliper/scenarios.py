"""CALI-185 (#296) slice A: a part's scenarios (its strength loads) and supports (what holds it) as data.

Theo, 2026-11-14: "I probably should be able to edit the scenarios or add new ones"; "every part needs to be able to have
the static 'doesn't move' fix point, and the loading stress specified … correctable, either with user input as text in the
right hand menu …"; and of a standard's case, "lowered, default to the standard, allow it to be edited".

- **Where they come from:** a part's script says them (``loads()``, ``HELD``). Edited, they're kept in ``design.yaml``
  (``Design.scenarios[part]``) and read in their place by every strength check, Lighten and carve (``load_study.prepare``),
  and so by the joint check (#301), which reads the same loads and supports. With no edit the script's are read, the very
  same items.
- **A scenario:** ``{"name", "amount", "unit": lb | kg | N, "direction": a unit vector (down by default), "factor", "lo",
  "hi" (the box it pushes on), "on"}``. A standard's case also keeps ``"standard"``, its numbers as the script gave them.
  Edited, it's named for what it is now ("EN 14183, edited: 100 kg (the standard is 150 kg)") and never says it meets the
  standard; :func:`standard` puts it back. Tipping cases stay the script's.
- **A support:** ``{"name", "lo", "hi"}``, or :data:`FLOOR`, the floor at the underside, as a part holds by default.
- **An edit writes a new version of the part** with the same script (action ``loads``): every check, Lighten and carve of it
  then reads "older version" through the path every reader already has, and none keeps a verdict from loads that are gone
  (Rule 6). Refused in words, with nothing written, where a row can't be acted on.
"""

from __future__ import annotations

import copy
import hashlib
import math
import re
from typing import Optional

#: A standard named in a case: "EN 14183", "ISO 7173", "ANSI/BIFMA X5.1", "ASTM F2057".
STANDARD = re.compile(r"\b(?:EN|ISO|ASTM|ANSI/BIFMA|BIFMA|ANSI)\s?[A-Z]?\d[\d.]*")
#: What holds a part that doesn't say: the floor at its underside.
FLOOR = {"name": "the floor", "floor": True}
UNITS = ("lb", "kg", "N")


def _per(unit: str) -> float:
    from .load_study import GRAVITY, LB

    return {"lb": LB, "kg": GRAVITY, "N": 1.0}[unit]


def _row(item: dict) -> dict:
    """A script's load as a scenario row."""
    if "force" in item:
        f = [float(v) for v in item["force"]]
        n = math.sqrt(sum(v * v for v in f)) or 1.0
        amount, unit, direction = round(n, 3), "N", [v / n for v in f]
    elif "kg" in item:
        amount, unit, direction = float(item["kg"]), "kg", [0.0, 0.0, -1.0]
    else:
        amount, unit, direction = float(item.get("lb") or 0.0), "lb", [0.0, 0.0, -1.0]
    row = {"name": str(item.get("name") or "a load"), "amount": amount, "unit": unit, "direction": direction,
           "factor": float(item.get("factor", 1.0)), "lo": [float(v) for v in item["lo"]],
           "hi": [float(v) for v in item["hi"]], "on": True}
    if STANDARD.search(row["name"]):
        row["standard"] = {k: copy.deepcopy(v) for k, v in row.items() if k != "on"}
    return row


def _key(sc: dict) -> str:
    """The name a row is matched to its script's load by: a standard's own, else its name."""
    return (sc.get("standard") or {}).get("name") or sc.get("name") or ""


def _script_rows(declared: dict) -> dict:
    """The script's strength loads as rows, by name."""
    return {r["name"]: r for r in (_row(ld) for ld in declared.get("loads") or []
                                   if isinstance(ld, dict) and not ld.get("tip"))}


def _sha(script: str) -> str:
    return hashlib.sha1(script.encode()).hexdigest()


def _said(store, pid: str) -> Optional[dict]:
    return (getattr(store.design, "scenarios", None) or {}).get(pid)


def get(store, pid: str) -> dict:
    """A part's scenarios and supports, as they're edited: ``{"scenarios", "supports", "overridden"}``. Each scenario
    also says ``said``, the name its checks use (an edited standard's is what it is now)."""
    got = _get(store, pid)
    for sc in got["scenarios"]:
        sc["said"] = name(sc)
    return got


def _get(store, pid: str) -> dict:
    said = _said(store, pid)
    from . import construction as C

    if said:
        rows = copy.deepcopy(said["scenarios"])
        script = _script_rows(C.declared(store, pid))
        for r in rows:                          # one never moved sits where its script's does now (#312 review)
            now = script.get(_key(r))
            if not r.get("moved") and now:
                r["lo"], r["hi"] = list(now["lo"]), list(now["hi"])
        return {"scenarios": rows, "supports": copy.deepcopy(said["supports"]), "overridden": True}
    declared = C.declared(store, pid)
    rows = [_row(ld) for ld in declared.get("loads") or [] if isinstance(ld, dict) and not ld.get("tip")]
    held = declared.get("held")
    supports = ([{"name": str(h.get("name") or f"support {i + 1}"), "lo": [float(v) for v in h["lo"]],
                  "hi": [float(v) for v in h["hi"]]} for i, h in enumerate(held)] if held else [dict(FLOOR)])
    return {"scenarios": rows, "supports": supports, "overridden": False}


def _differs(sc: dict, std: dict) -> bool:
    def close(a, b):
        return all(abs(float(x) - float(y)) < 1e-6 for x, y in zip(a, b)) if isinstance(a, list) else \
            (abs(float(a) - float(b)) < 1e-6 if isinstance(a, (int, float)) else a == b)

    return any(not close(sc.get(k), std.get(k)) for k in ("amount", "unit", "direction", "factor", "lo", "hi"))


def _num(v: float) -> str:
    return f"{v:g}"


def name(sc: dict) -> str:
    """A scenario's name as every reader says it. A standard's case edited from the standard is named for what it is now,
    never the standard's own words (#296: no card, scorecard line or book page says it meets the standard)."""
    std = sc.get("standard")
    if std and _differs(sc, std):
        label = (STANDARD.search(std["name"]) or STANDARD.search(sc["name"]))
        label = label.group(0) if label else "the standard"
        return f"{label}, edited: {_num(sc['amount'])} {sc['unit']} (the standard is {_num(std['amount'])} {std['unit']})"
    return std["name"] if std else sc["name"]


def standard(sc: dict) -> dict:
    """A standard's case back at the standard's numbers (#296: "Back to the standard puts it back")."""
    std = sc.get("standard")
    if not std:
        return dict(sc)
    return {**copy.deepcopy(std), "standard": copy.deepcopy(std), "on": sc.get("on", True)}


def _load(sc: dict, script: Optional[dict] = None) -> dict:
    f = float(sc["amount"]) * _per(sc["unit"])
    now = (script or {}).get(_key(sc)) if not sc.get("moved") else None
    box = (now["lo"], now["hi"]) if now else (sc["lo"], sc["hi"])        # never moved: where its script's is now
    return {"name": name(sc), "force": [f * float(v) for v in sc["direction"]], "factor": float(sc["factor"]),
            "lo": list(box[0]), "hi": list(box[1])}


def loads(store, pid: str, declared: dict) -> list:
    """The strength loads a check reads, as ``loads()`` items: the edited scenarios that are on, else the script's own
    (the very same items, so a part never edited checks byte for byte as it did)."""
    said = _said(store, pid)
    if not said:
        return [ld for ld in declared.get("loads") or [] if not (isinstance(ld, dict) and ld.get("tip"))]
    script = _script_rows(declared)
    return [_load(sc, script) for sc in said["scenarios"] if sc.get("on", True)]


def held(store, pid: str, declared: dict):
    """What holds the part, as ``HELD`` items, or None for the floor: the edited supports, else the script's."""
    said = _said(store, pid)
    if not said:
        return declared.get("held")
    rows = [s for s in said["supports"] if not s.get("floor")]
    if not rows:
        return None                             # the floor alone: as a part holds by default
    out = [{"name": s["name"], "lo": list(s["lo"]), "hi": list(s["hi"])} for s in rows]
    if any(s.get("floor") for s in said["supports"]):     # the floor beside them, kept (#312 review: it was dropped)
        out.append({"name": "the floor", "floor": True})
    return out


def off(store, pid: str) -> list:
    """The scenarios turned off, by name: said where the part's strength is (#296)."""
    said = _said(store, pid)
    return [name(sc) for sc in (said or {}).get("scenarios") or [] if not sc.get("on", True)]


def _vec(v, what: str) -> list:
    try:
        out = [float(x) for x in v]
    except (TypeError, ValueError):
        out = []
    if len(out) != 3 or not all(math.isfinite(x) for x in out):
        raise ValueError(f"{what} is three numbers (x, y, z, mm)")
    return out


def _clean(store, pid: str, scenarios: list, supports: list) -> tuple[list, list]:
    from . import construction as C
    from . import load_study as L
    from .consistency import tolerance

    mesh = store.part_geometry(pid).require_mesh()
    script = _script_rows(C.declared(store, pid))
    # a standard's numbers are its script's, or kept with the edit: never the request's (#312 review)
    standards = {r["standard"]["name"]: r["standard"] for r in script.values() if r.get("standard")}
    for r in (_said(store, pid) or {}).get("scenarios") or []:
        if r.get("standard"):
            standards.setdefault(r["standard"]["name"], r["standard"])
    rch = L.reach(tolerance(mesh), 0.0)
    rows = []
    for i, sc in enumerate(scenarios or []):
        nm = str((sc or {}).get("name") or "").strip()
        if not nm:
            raise ValueError(f"scenario {i + 1} needs a name: what it is, in a few words")
        unit = sc.get("unit")
        if unit not in UNITS:
            raise ValueError(f"'{nm}': how much is in lb, kg or N")
        try:
            amount, factor = float(sc.get("amount")), float(sc.get("factor", 1.0))
        except (TypeError, ValueError):
            raise ValueError(f"'{nm}': how much and its margin are numbers") from None
        if not (amount > 0 and factor > 0 and math.isfinite(amount) and math.isfinite(factor)):
            raise ValueError(f"'{nm}': the load and its margin must be more than nothing")
        d = _vec(sc.get("direction", [0, 0, -1]), f"'{nm}': which way it pushes")
        n = math.sqrt(sum(v * v for v in d))
        if n < 1e-9:
            raise ValueError(f"'{nm}': which way it pushes can't be nothing: down is (0, 0, -1)")
        lo, hi = _vec(sc.get("lo"), f"'{nm}': where it pushes, lo,"), _vec(sc.get("hi"), f"'{nm}': where it pushes, hi,")
        lo, hi = [min(a, b) for a, b in zip(lo, hi)], [max(a, b) for a, b in zip(lo, hi)]
        on, gap = L.touches(mesh, (lo, hi), rch)
        if not on:
            raise ValueError(f"'{nm}' doesn't touch the part: it pushes on thin air, {gap:.1f} mm from its nearest surface")
        row = {"name": nm, "amount": amount, "unit": unit, "direction": [v / n for v in d], "factor": factor,
               "lo": lo, "hi": hi, "on": bool(sc.get("on", True))}
        std = standards.get((sc.get("standard") or {}).get("name"))
        if std:
            row["standard"] = copy.deepcopy(std)
        was = script.get(_key(row))                  # where its script puts it: unmoved follows the shape (#312 review)
        row["moved"] = not (was and all(abs(a - b) < 1e-6 for a, b in zip(lo + hi, was["lo"] + was["hi"])))
        rows.append(row)
    if not any(r["on"] for r in rows):
        raise ValueError("turn at least one scenario on: with none, there's nothing to check it holds")
    held_rows = []
    for i, s in enumerate(supports or [dict(FLOOR)]):
        if s.get("floor"):
            held_rows.append(dict(FLOOR))
            continue
        nm = str(s.get("name") or "").strip() or f"support {i + 1}"
        lo, hi = _vec(s.get("lo"), f"'{nm}': where it's held, lo,"), _vec(s.get("hi"), f"'{nm}': where it's held, hi,")
        lo, hi = [min(a, b) for a, b in zip(lo, hi)], [max(a, b) for a, b in zip(lo, hi)]
        on, gap = L.touches(mesh, (lo, hi), rch)
        if not on:
            raise ValueError(f"'{nm}' doesn't touch the part: nothing holds it there, {gap:.1f} mm from its nearest "
                             f"surface")
        held_rows.append({"name": nm, "lo": lo, "hi": hi})
    return rows, held_rows


def _summary(rows: list) -> str:
    on = [r for r in rows if r["on"]]
    return (f"loads: {len(on)} scenario{'s' if len(on) != 1 else ''}"
            + (f" ({len(rows) - len(on)} off)" if len(rows) != len(on) else ""))


def _mirror(store, pid: str) -> None:
    from . import mirror

    got = mirror.of(store.read_script(pid))
    if got is not None:
        raise ValueError(f"{pid} mirrors {got['source']}: edit {got['source']}'s loads, which its mirror is checked to")


def _changes(old: list, new: list) -> str:
    """What an edit changed, row by row, for its history line (#312 review: "loads: 3 scenarios" said too little)."""
    was = {_key(r): r for r in old}
    out = []
    for r in new:
        o = was.pop(_key(r), None)
        nm = name(o) if o else r["name"]
        if o is None:
            out.append(f"added '{r['name']}'")
            continue
        if (o["amount"], o["unit"]) != (r["amount"], r["unit"]):
            out.append(f"{nm}: {_num(o['amount'])} → {_num(r['amount'])} {r['unit']}"
                       if o["unit"] == r["unit"] else f"{nm}: {_num(o['amount'])} {o['unit']} → {_num(r['amount'])} {r['unit']}")
        if any(abs(a - b) > 1e-6 for a, b in zip(o["direction"], r["direction"])):
            out.append(f"{nm}: pushes another way")
        if abs(o["factor"] - r["factor"]) > 1e-9:
            out.append(f"{nm}: margin {_num(o['factor'])} → {_num(r['factor'])}")
        if any(abs(a - b) > 1e-6 for a, b in zip(o["lo"] + o["hi"], r["lo"] + r["hi"])):
            out.append(f"{nm}: moved")
        if o.get("on", True) != r["on"]:
            out.append(f"{nm}: {'on' if r['on'] else 'off'}")
    out += [f"removed '{name(o)}'" for o in was.values()]
    return "loads: " + ("; ".join(out) if out else "saved as they were")


def put(store, pid: str, scenarios: list, supports: list) -> int:
    """Keep a part's scenarios and supports in ``design.yaml`` and write a new version of it, the same script, so every
    check of it is out of date. Returns the version. Raises ValueError, in words, with nothing written."""
    _mirror(store, pid)
    old = get(store, pid)["scenarios"]
    rows, held_rows = _clean(store, pid, scenarios, supports)
    before = copy.deepcopy(getattr(store.design, "scenarios", None) or {})
    script = store.read_script(pid)
    store.design.scenarios = {**before, pid: {"scenarios": rows, "supports": held_rows, "script_sha": _sha(script)}}
    try:
        return store.write_part(pid, script, action="loads", feedback=_changes(old, rows))
    except Exception:
        store.design.scenarios = before
        store.save()
        raise


def clear(store, pid: str) -> int:
    """Back to the script's own loads and supports: a new version too, so a check of the edited ones is out of date.
    With nothing edited, nothing is written (#312 review)."""
    before = copy.deepcopy(getattr(store.design, "scenarios", None) or {})
    if pid not in before:
        return store.design.part(pid).version
    store.design.scenarios = {k: v for k, v in before.items() if k != pid}
    try:
        return store.write_part(pid, store.read_script(pid), action="loads", feedback="loads: back to its script's")
    except Exception:
        store.design.scenarios = before
        store.save()
        raise


def drift(store, pid: str) -> str:
    """What to tell the person when the part's shape changed since they edited its loads (#312 review): the rows they
    moved stayed where they put them, named, and any that no longer touch it. Rows never moved follow the script's boxes,
    so they're not said. "" when there's nothing to say."""
    said = _said(store, pid)
    if not said:
        return ""
    moved = [r for r in said["scenarios"] if r.get("moved") and r.get("on", True)]
    if not moved or said.get("script_sha") == _sha(store.read_script(pid)):
        return ""
    from . import load_study as L
    from .consistency import tolerance

    try:
        mesh = store.part_geometry(pid).require_mesh()
    except Exception:  # noqa: BLE001 — no shape to say it against: said plainly
        mesh = None
    rch = L.reach(tolerance(mesh), 0.0) if mesh is not None else 0.0
    said_rows = []
    for r in moved:
        on, gap = L.touches(mesh, (r["lo"], r["hi"]), rch) if mesh is not None else (True, 0.0)
        said_rows.append(f"'{name(r)}' stayed where you put it" if on
                         else f"'{name(r)}' doesn't touch it any more ({gap:.0f} mm off its nearest surface)")
    it = "it" if len(moved) == 1 else "them"
    return (f"Its shape changed since you edited its loads: {'; '.join(said_rows)}. Check {it}, and move {it} under "
            f"Scenarios and supports, or put {it} back to its script's there.")
