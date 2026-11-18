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
    """A part's scenarios and supports, as the editor shows them: ``{"scenarios", "supports", "overridden"}``. Each row
    says ``said`` (the name its checks use), ``of`` (the script case it is, or None for one the person added), ``source``
    (``script``, ``edited`` or ``added``), and where the design changed under an edit, ``conflict`` and ``design`` (the
    script's case now), so the page can offer "take the design's"."""
    from . import construction as C

    declared = C.declared(store, pid)
    said = _said(store, pid)
    if not said:
        rows = [{**r, "of": k, "source": "script"} for k, r in _script_rows(declared).items()]
        got = {"scenarios": rows, "supports": _supports(declared), "overridden": False}
    else:
        rows = [{**e["row"], "of": e["of"], "source": e["source"], "new": e.get("new", False),
                 **({"conflict": e["conflict"], "design": e.get("design"), "checked": e.get("checked")}
                    if e.get("conflict") else {})}
                for e in _effective(said, declared)]
        got = {"scenarios": rows, "supports": copy.deepcopy(said["supports"]), "overridden": True}
    for sc in got["scenarios"]:
        sc["said"] = name(sc)
    return got


def _supports(declared: dict) -> list:
    """What holds a part as its script says, as the editor's rows: its HELD, else the floor."""
    held = declared.get("held")
    return ([{"name": str(h.get("name") or f"support {i + 1}"), "lo": [float(v) for v in h["lo"]],
              "hi": [float(v) for v in h["hi"]]} for i, h in enumerate(held)] if held else [dict(FLOOR)])


def _same_supports(a: list, b: list) -> bool:
    def key(s):
        return ("floor",) if s.get("floor") else (s["name"], *[round(float(v), 6) for v in list(s["lo"]) + list(s["hi"])])

    return sorted(map(key, a)) == sorted(map(key, b))


def _edits(said: dict) -> list:
    """An override's edits: ``{"of": the script case, or None for one added, "row", "base": the script case as it was
    when edited}``. An override kept before #312's re-check held whole rows: each read as an edit of its namesake."""
    if "edits" in said:
        return said["edits"]
    return [{"of": _key(r), "row": r, "base": None} for r in said.get("scenarios") or []]


def _effective(said: dict, declared: dict) -> list:
    """The rows a check reads, edits laid on the script (#312 re-check: an override replaced the script's loads, so a
    case the design added, or changed under an edit, went unchecked and unsaid). Each ``{"row", "of", "source", ...}``:
    every script case as the script has it now, unless the person edited it; the edit then, its box the script's where
    they never moved it; an edit whose case is gone, still read, with ``conflict``; then the rows they added."""
    script = _script_rows(declared)
    edits = _edits(said)
    by_of = {e["of"]: e for e in edits if e.get("of")}
    seen = set(said.get("seen") or script)
    out = []
    for k, sc in script.items():
        e = by_of.get(k)
        if e is None:                                        # never edited: the script's, entirely
            out.append({"row": copy.deepcopy(sc), "of": k, "source": "script", "new": k not in seen})
            continue
        r = copy.deepcopy(e["row"])
        if not r.get("moved"):                               # never moved: where its script's is now
            r["lo"], r["hi"] = list(sc["lo"]), list(sc["hi"])
        base = e.get("base")
        got = {"row": r, "of": k, "source": "edited"}
        if base and (_numbers(base, sc) or base.get("name") != sc.get("name")):
            got.update(conflict=_changed(r, sc), design=copy.deepcopy(sc), **_both(r, sc))
        out.append(got)
    for e in edits:
        if e.get("of") and e["of"] not in script:            # its case is gone from the design: still read, and asked
            out.append({"row": copy.deepcopy(e["row"]), "of": e["of"], "source": "edited",
                        "conflict": f"you'd edited '{e['of']}'; the design no longer has it", "design": None,
                        "checked": "yours is still checked until you choose"})
        elif not e.get("of"):
            out.append({"row": copy.deepcopy(e["row"]), "of": None, "source": "added"})
    return out


def _demand(r: dict) -> float:
    return float(r["amount"]) * _per(r["unit"]) * float(r["factor"])


def _both(mine: dict, now: dict) -> dict:
    """What an open conflict checks until the person chooses (#312 third round), never greener than either: where theirs and
    the design's order (the same name, way and box), the more demanding, said which; where they don't, both, each under
    its own name. A row of theirs turned off: the design's."""
    def unit(v):
        n = math.sqrt(sum(float(x) ** 2 for x in v)) or 1.0
        return [float(x) / n for x in v]

    theirs = f"{_num(now['amount'])} {now['unit']}"
    if not mine.get("on", True):
        return {"checks": [now], "checked": f"checked at the design's {theirs} until you choose; yours is off"}
    yours = f"{_num(mine['amount'])} {mine['unit']}"
    same = (mine["name"] == now["name"]
            and all(abs(a - b) < 1e-6 for a, b in zip(unit(mine["direction"]), unit(now["direction"])))
            and all(abs(float(a) - float(b)) < 1e-6 for a, b in zip(list(mine["lo"]) + list(mine["hi"]),
                                                                    list(now["lo"]) + list(now["hi"]))))
    if same:
        if _demand(now) > _demand(mine) * (1 + 1e-9):
            return {"checks": [now], "checked": f"checked at the design's {theirs} until you choose; yours is {yours}"}
        return {"checks": [mine], "checked": f"checked at yours, {yours}, until you choose; the design's is {theirs}"}
    a, b = copy.deepcopy(mine), copy.deepcopy(now)
    if name(a) == name(b):
        a["name"], b["name"] = f"{a['name']} (yours)", f"{b['name']} (the design's)"
    return {"checks": [a, b], "checked": "both checked until you choose"}


def asked(store, pid: str) -> list:
    """A part's open conflicts, each in words with what's checked until the person chooses (#312 third round): for the
    reply, the card, the scorecard's strength note, the release and a Save's message. [] where none."""
    said = _said(store, pid)
    if not said:
        return []
    from . import construction as C

    return [_asked(e) for e in _effective(said, C.declared(store, pid)) if e.get("conflict")]


def _asked(e: dict) -> str:
    return f"{e['conflict']}: {e['checked']}" if e.get("checked") else e["conflict"]


def _numbers(a: dict, b: dict) -> bool:
    """Whether two rows ask different loads: the box left out, since a shape change moves it and unmoved rows follow."""
    return _differs({**a, "lo": b["lo"], "hi": b["hi"]}, b)


def _changed(mine: dict, now: dict) -> str:
    """What the design changed under an edit, in words."""
    nm = now["name"] if now["name"] == mine["name"] else mine["name"]
    if (mine["amount"], mine["unit"]) != (now["amount"], now["unit"]):
        return (f"you'd edited '{nm}' to {_num(mine['amount'])} {mine['unit']}; the design now asks "
                f"{_num(now['amount'])} {now['unit']}")
    return f"you'd edited '{nm}'; the design has changed it since"


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
        same = not any(abs(float(a) - float(b)) > 1e-6 for a, b in zip(
            [sc["amount"], sc["factor"], *sc["direction"]], [std["amount"], std["factor"], *std["direction"]])) \
            and sc["unit"] == std["unit"]
        if same:                                             # only moved: said as that (#312 re-check)
            return f"{label}, moved: {_num(sc['amount'])} {sc['unit']}, somewhere else than the standard says"
        return f"{label}, edited: {_num(sc['amount'])} {sc['unit']} (the standard is {_num(std['amount'])} {std['unit']})"
    return std["name"] if std else sc["name"]


def standard(sc: dict) -> dict:
    """A standard's case back at the standard's numbers (#296: "Back to the standard puts it back")."""
    std = sc.get("standard")
    if not std:
        return dict(sc)
    return {**copy.deepcopy(std), "standard": copy.deepcopy(std), "on": sc.get("on", True)}


def _load(sc: dict) -> dict:
    f = float(sc["amount"]) * _per(sc["unit"])
    return {"name": name(sc), "force": [f * float(v) for v in sc["direction"]], "factor": float(sc["factor"]),
            "lo": list(sc["lo"]), "hi": list(sc["hi"])}


def says_loads(store, pid: str, script: Optional[str] = None) -> bool:
    """Whether a part says what it must hold (#327): its script's ``loads()``, or a case the person keeps in the editor:
    one they added, or an edit whose case the design has since dropped (its check still reads it, #312). A save with
    every case off is refused, so any of them is one it checks. What the page's ``p.loads`` is, so a part with no ``loads()`` given one there shows its check,
    its results and Lighten, as one whose script says it."""
    if script is None:
        script = store.read_script(pid) if store.is_scripted(pid) else ""
    if "def loads(" in script:
        return True
    said = _said(store, pid)
    return bool(said) and bool(_edits(said))


def loads(store, pid: str, declared: dict) -> list:
    """The strength loads a check reads, as ``loads()`` items: the edited scenarios that are on, else the script's own
    (the very same items, so a part never edited checks byte for byte as it did)."""
    said = _said(store, pid)
    if not said:
        return [ld for ld in declared.get("loads") or [] if not (isinstance(ld, dict) and ld.get("tip"))]
    return [_load(r) for e in _effective(said, declared) for r in e.get("checks", [e["row"]]) if r.get("on", True)]


def restored(had: Optional[dict], now: Optional[dict], target: int) -> str:
    """What a roll-back to ``target`` did to a part's loads, in words, for the reply and its history line (#312 review and
    re-check): back to the script's, naming the edits undone, or as they were at that version. "" where they're the same."""
    if had == now:
        return ""
    if now is None:
        undone = [name(e["row"]) for e in _edits(had or {})]   # only rows edited are kept: each one is undone
        return "its loads are the script's again" + (f" (undone: {'; '.join(undone)})" if undone else "")
    return f"its loads are as they were at v{target}"


def declared(store, pid: str) -> dict:
    """A part's declarations with the loads its check reads (#312 re-check: the edge warning and the seat's unchecked
    cases read the script's, so an edge case turned off still passed as checked): its edited scenarios that are on and
    its supports, beside the script's tipping cases, which no scenario edits. The script's own where nothing's edited."""
    from . import construction as C

    d = C.declared(store, pid)
    if not d or d.get("error") or not _said(store, pid):
        return d
    tips = [ld for ld in d.get("loads") or [] if isinstance(ld, dict) and ld.get("tip")]   # script's loads: tipping cases
    return {**d, "loads": loads(store, pid, d) + tips, "held": held(store, pid, d)}


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
    if not said:
        return []
    from . import construction as C

    return [name(e["row"]) for e in _effective(said, C.declared(store, pid)) if not e["row"].get("on", True)]


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
    for r in (e["row"] for e in _edits(_said(store, pid) or {})):
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
        of = sc["of"] if "of" in sc else (_key(row) if _key(row) in script else None)
        of = of if of in script or of in {e.get("of") for e in _edits(_said(store, pid) or {})} else None
        was = script.get(of) if of else None         # where its script puts it: unmoved follows the shape (#312 review)
        row["moved"] = not (was and all(abs(a - b) < 1e-6 for a, b in zip(lo + hi, was["lo"] + was["hi"])))
        rows.append((row, of, bool(sc.get("keep"))))     # Keep mine, pressed on an open conflict (#312 third round)
    if not any(r["on"] for r, *_ in rows):
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
    key = lambda r: r.get("of") or _key(r)        # noqa: E731 — a row by the script case it is, else its name
    was = {key(r): r for r in old}
    out = []
    for r in new:
        o = was.pop(key(r), None)
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
    from . import construction as C

    old = get(store, pid)["scenarios"]
    rows, held_rows = _clean(store, pid, scenarios, supports)
    declared = C.declared(store, pid)
    script_rows = _script_rows(declared)
    prev = {e["of"]: e for e in _edits(_said(store, pid) or {}) if e.get("of")}
    edits, kept = [], set()
    for row, of, keep in rows:               # each an edit on its script case, or one added (#312 re-check)
        sc = script_rows.get(of) if of else None
        if sc is not None:
            kept.add(of)
            if not _differs(row, sc) and row["name"] == sc["name"] and row["on"]:
                continue                     # unchanged: the script's, entirely (and Take the design's settles it)
            was = (prev.get(of) or {}).get("base")
            open_ = not keep and was is not None and (_numbers(was, sc) or was.get("name") != sc.get("name"))
            # a Save settles only the conflicts acted on: one left as it was stays open (#312 third round)
            edits.append({"of": of, "row": row, "base": copy.deepcopy(was if open_ else sc)})
        elif of:                             # its case gone from the design: theirs, asked, till they keep or remove it
            edits.append({"of": None, "row": row} if keep else {"of": of, "row": row, "base": None})
        else:
            edits.append({"of": None, "row": row})
    for k, sc in script_rows.items():        # a script case taken off the list: off, not gone
        if k not in kept:
            edits.append({"of": k, "row": {**copy.deepcopy(sc), "on": False, "moved": False}, "base": copy.deepcopy(sc)})
    before = copy.deepcopy(getattr(store.design, "scenarios", None) or {})
    script = store.read_script(pid)
    if not edits and _same_supports(held_rows, _supports(declared)):   # nothing of theirs left: no override (#312)
        after = {k: v for k, v in before.items() if k != pid}
    else:
        after = {**before, pid: {"edits": edits, "supports": held_rows, "script_sha": _sha(script),
                                 "seen": list(script_rows)}}
    if after == before:                      # saved as they were: no new version, every check of it still current
        return store.design.part(pid).version
    store.design.scenarios = after
    new = get(store, pid)["scenarios"]
    still = asked(store, pid)
    try:
        return store.write_part(pid, script, action="loads", feedback=_changes(old, new)
                                + (f"; still open: {'; '.join(still)}" if still else ""))
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
    """What to tell the person when the part changed since they edited its loads (#312 review and re-check). The rows they
    moved stayed where they put them, and any that no longer touch it are named. Where the design's own cases changed: a
    case it added (checked), an edit whose case it changed or dropped ("keep yours, or take the design's?"), and the edits
    of theirs still read. Rows never edited are the script's, and rows never moved follow its boxes, so they're not said.
    "" when there's nothing to say."""
    said = _said(store, pid)
    if not said:
        return ""
    shape = said.get("script_sha") != _sha(store.read_script(pid))
    from . import construction as C
    from . import load_study as L
    from .consistency import tolerance

    declared = C.declared(store, pid)
    entries = _effective(said, declared)
    out = []
    moved = [e["row"] for e in entries if shape and e["source"] != "script" and e["row"].get("moved")
             and e["row"].get("on", True)]
    if moved:
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
        out.append(f"Its shape changed since you edited its loads: {'; '.join(said_rows)}. Check {it}, and move {it} under "
                   f"Scenarios and supports, or put {it} back to its script's there.")
    asks = [f"{_asked(e)}: {'keep yours, or take the design' + chr(39) + 's?' if e.get('design') else 'keep yours, or remove it?'}"
            for e in entries if e.get("conflict")]                 # open till chosen, said each time (#312 third round)
    added = [name(e["row"]) for e in entries if e.get("new")]
    if asks or added:                                        # the design's own cases changed under the edit
        kept = [name(e["row"]) if name(e["row"]) != e["row"]["name"]           # a standard's says its own number
                else f"'{name(e['row'])}' at {_num(e['row']['amount'])} {e['row']['unit']}" for e in entries
                if e["source"] == "edited" and not e.get("conflict") and e["row"].get("on", True)]
        items = ([f"the design added '{n}': it's checked" for n in added]
                 + ([f"yours kept: {', '.join(kept)}"] if kept else []) + asks)       # its questions last
        line = "Its loads changed in the design since you edited them: " + "; ".join(items)
        out.append(line if line.endswith("?") else line + ".")                       # never "?." (#312 third round)
    return " ".join(out)
