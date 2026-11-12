"""CALI-108 (#108, the backend) — a part's exact numbers, set by hand, with no Claude call.

Theo, driving the bar stool: "the advantage to manual cad is the ability to specify things precisely". A part's script
keeps its dimensions in ``PARAMS`` (mm, the scripts' unit), with bounds in ``RANGES``, and ``build(params)`` merges
overrides. So an exact number needs no designer: :func:`listing` says each one in plain words (its comment), and
:func:`set_value` sets one. It converts the person's unit to mm, refuses a value outside its range (saying the range),
builds the part with it first, then rewrites only that ``PARAMS`` value (``aero.set_params``: by its source position,
so its comment and every other line stay exactly), writes a new version whose history says "set wall_t to 5 mm by
hand", and measures the design again. A value the build ignores or clamps is said: the part's shape didn't move, or
``build()`` never reads it (#107: 12.7 mm asked, 6.3 mm built).
"""

from __future__ import annotations

import io
import re
import tokenize
from fractions import Fraction
from typing import Optional

from . import aero
from .design import DesignStore

IN = 25.4
#: The person's units, to the scripts' millimetres.
TO_MM = {"mm": 1.0, "in": IN, "ft": 12 * IN, "cm": 10.0, "m": 1000.0}


def notes(script: str) -> dict[str, str]:
    """Each ``PARAMS`` key's comment, its name in plain words: the comment on its line, or the comment line just
    above it."""
    node = aero._params_node(__import__("ast").parse(script))
    if node is None:
        return {}
    comments: dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(script).readline):
            if tok.type == tokenize.COMMENT:
                comments[tok.start[0]] = tok.string.lstrip("#").strip()
    except (tokenize.TokenError, IndentationError):
        pass
    lines = script.splitlines()
    out = {}
    for k in node.keys:
        if hasattr(k, "value") and isinstance(k.value, str):
            n = k.lineno
            above = comments.get(n - 1) if n >= 2 and lines[n - 2].strip().startswith("#") else None
            out[k.value] = comments.get(n) or above or ""
    return out


#: What a number is, by what the script says (#147 review, the foreman's call: never by whether it's written 6 or 6.0).
_LENGTH_UNIT = re.compile(r"\b(?:mm|cm|millimet(?:re|er)s?|inch(?:es)?)\b|\d\s*(?:in\b|\")", re.I)
_LENGTH_NAME = re.compile(r"(?:_t|_r|_d|_h|_w|_len|_l)$|width|height|depth|radius|diameter|thick|wall|fillet|gap|length|"
                          r"offset|clearance|chamfer|_z$|_x$|_y$", re.I)
#: A length, as its comment says it in words ("width of the box", "how tall it stands").
_LENGTH_WORD = re.compile(r"\b(?:width|wide|height|tall|depth|deep|radius|diameter|thickness|thick|wall|fillet|gap|"
                          r"length|long|offset|clearance)\b", re.I)
_COUNT = re.compile(r"rows|cols|columns|segments|holes|facets|teeth|steps|slats|^n_|_count$|\bcount\b|number of|"
                    r"how many", re.I)
_RATIO = re.compile(r"taper|infill|ratio|frac|percent|share", re.I)
#: A choice, as its comment lists it: "1 = straight, 2 = round", "0: no edges; 1: front and back edges".
_CHOICE = re.compile(r"(?:^|[\s,;(])\d+\s*[=:]\s*[a-z]", re.I)


def unit_of(name: str, note: str) -> str:
    """What a number is, as the script says it (#147 review, the foreman's order, on Theo's own scripts):
    1. a length unit in its comment wins: "mm" (``rib_v``, "vertical rib between rows mm", is a rib's width);
    2. a comment that lists choices ("1 = straight, 2 = round") is a "choice" (``shoulder``), no unit;
    3. an angle ("deg"), then a count or a ratio by its name or comment, then a length by its name or a length word
       in its comment ("mm");
    4. otherwise "": not known, so a unit given with it is refused (``set_value``), never dropped."""
    if _LENGTH_UNIT.search(note):
        return "mm"
    if len(_CHOICE.findall(note)) >= 2:
        return "choice"
    if re.search(r"\bdeg|degree|angle|°", f"{name} {note}", re.I):
        return "deg"
    if _COUNT.search(name) or _COUNT.search(note):
        return "count"
    if _RATIO.search(name) or _RATIO.search(note):
        return "ratio"
    if _LENGTH_NAME.search(name) or _LENGTH_WORD.search(note):
        return "mm"
    return ""


def reads(script: str, name: str) -> bool:
    """Whether the script uses a ``PARAMS`` entry anywhere but in ``PARAMS`` and ``RANGES`` themselves (``p["name"]``,
    ``params.get("name")``): one it never reads changes nothing."""
    import ast

    tree = ast.parse(script)
    skip = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in (aero.PARAMS_NAME, "RANGES")
                                                for t in node.targets):
            skip.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and node.value == name and getattr(node, "lineno", 0) not in skip):
            return True
    return False


def listing(store: DesignStore, pid: str) -> list[dict]:
    """Every ``PARAMS`` entry of a scripted part: ``{name, note, value, unit, range, read}``, values in mm (lengths),
    ranges as the script says them, ``read``: whether ``build()`` and the rest use it."""
    if not store.is_scripted(pid):
        raise ValueError(f"'{pid}' isn't a script: it has no numbers to set")
    script = store.read_script(pid)
    values = aero.read_params(script) or {}
    said, ranges = notes(script), aero.read_ranges(script)
    return [{"name": k, "note": said.get(k, ""), "value": v, "unit": unit_of(k, said.get(k, "")),
             "range": list(ranges[k]) if k in ranges else None, "read": reads(script, k)}
            for k, v in values.items()]


def _said(value: float, unit: str) -> str:
    """A number as it was set, exactly: the record of an exact edit never rounds it (3/8 in, not 0.4 in)."""
    if unit == "in":
        n = round(value * 32)
        if abs(value * 32 - n) > 0.001:
            return f"{value:.4f}".rstrip("0").rstrip(".") + " in"
        whole, rest = divmod(n, 32)
        frac = str(Fraction(rest, 32)) if rest else ""
        return f"{whole or ''} {frac}".strip() + " in" if whole or frac else "0 in"
    return f"{value:g} {unit}".strip()


def _shape(g) -> tuple:
    m = g.require_mesh()
    return (round(float(abs(m.volume)), 1), tuple(round(float(v), 2) for v in m.bounds.ravel()))


def _radii(geometry) -> set:
    """The radii of a solid's cylinders, in mm: the fillets and holes it has."""
    try:
        from OCP.BRepAdaptor import BRepAdaptor_Surface  # type: ignore

        solid = geometry.solid
        solid = solid.val() if hasattr(solid, "val") else solid
        return {round(BRepAdaptor_Surface(f.wrapped).Cylinder().Radius(), 2) for f in solid.Faces() if f.geomType() == "CYLINDER"}
    except Exception:  # noqa: BLE001 — not measured, so nothing's said
        return set()


def _probe(name: str, asked_mm: float, geometry, before) -> str:
    """What the built part shows of a number, only where the measurement is that number's own (#107's fillet: 12.7 asked,
    6.3 built; #171 review: "built 3 mm" named the mesh openings' corners, and "thinnest wall" a feathered lip elsewhere).
    A fillet's or hole's radius that appeared when this one number changed is its own. Anything else says nothing."""
    lname = name.lower()
    if "fillet" not in lname and "hole" not in lname or before is None:
        return ""
    made = _radii(geometry) - _radii(before)
    if not made:
        return ""
    want = asked_mm / 2 if re.search(r"_d$|diameter|dia\b", lname) else asked_mm
    got = min(made, key=lambda r: abs(r - want))
    if abs(got - want) <= max(0.02 * want, 0.01):
        return ""
    built = got * 2 if want != asked_mm else got
    return f"asked {asked_mm:g} mm, built {built:.3g} mm (the closest {'hole' if 'hole' in lname else 'fillet'})"


def _to_script(e: dict, value: float, unit: Optional[str]) -> tuple[float, str, list[str]]:
    """One typed number as its script keeps it: ``(number, how it's said, notes)``. Raises ValueError, saying why, for
    a unit it can't read or a value outside its range."""
    name, plain, notes = e["name"], e["name"].replace("_", " "), []
    if e["unit"] == "mm":                         # only a length converts (#147 review)
        unit = unit or "mm"
        if unit not in TO_MM:
            raise ValueError(f"{plain} is a length: give it in mm or in, not {unit!r}")
        mm = float(value) * TO_MM[unit]
    elif e["unit"] in ("count", "ratio", "choice"):
        if unit not in (None, "", e["unit"]):
            raise ValueError(f"{plain} is a {e['unit']}: give a number, no unit")
        mm = float(value)
    elif e["unit"] == "deg":
        if unit not in (None, "", "deg"):
            raise ValueError(f"{plain} is an angle: give it in degrees")
        mm = float(value)
    else:                                         # not known: a unit given is refused, never dropped (#147 review)
        if unit not in (None, ""):
            raise ValueError(f"I don't know if {name} is a length: give it in mm, without a unit")
        mm = float(value)                         # taken as it is, said so
        notes.append(f"{name} has no unit in its script, so {mm:g} is taken as it is, not converted")
    lo_hi = e["range"]
    if not lo_hi:                                 # allowed, but said (#147 review)
        notes.append(f"no range is set for {name} in the script, so it isn't checked")
    if lo_hi and not (lo_hi[0] - 1e-9 <= mm <= lo_hi[1] + 1e-9):
        unit_said = e["unit"] or ""
        raise ValueError(f"{name} must be between {lo_hi[0]:g} and {lo_hi[1]:g} {unit_said}".rstrip()
                         + f": {_said(float(value), unit) if e['unit'] == 'mm' else f'{mm:g}'} is outside it")
    said = (_said(float(value), unit) if e["unit"] == "mm" else f"{mm:g} deg" if e["unit"] == "deg" else f"{mm:g}")
    return mm, said, notes


def set_values(store: DesignStore, pid: str, changes: list[dict]) -> dict:
    """Set a part's numbers by hand, ``[{name, value, unit}]``, as one change: no Claude call, built once with all of
    them, one new version, all or none (numbers that only work together can't leave a half-way part). Returns
    ``{version, said, value, moved, report, failed, notes, warning}``; raises ValueError, saying why, for a name it doesn't have, a
    unit it can't read, a value outside its range, or values the part won't build with (nothing written then)."""
    from . import load_study, mirror, sandbox

    source = mirror.source_of(store, pid)
    if source:                                    # a mirror's numbers are its source's: set there, said (#246 review)
        got = set_values(store, source, changes)
        return {**got, "said": f"{pid} mirrors {source}: I changed {source}, and {pid} follows it. {got['said']}",
                "part": source}
    if not changes:
        raise ValueError("there's no number to set")
    names = [c["name"] for c in changes]
    if len(set(names)) < len(names):
        raise ValueError("one of those numbers is set twice")
    from . import carve

    if carve.carved(store.read_script(pid)):          # its shape is the carve's mesh: its numbers only move its loads (#171)
        raise ValueError("it's been carved, so its numbers don't change its shape. Say \"roll it back\" to take the carve "
                         "off, set them, then carve it again")
    entries = {e["name"]: e for e in listing(store, pid)}
    for name in names:
        if name not in entries:
            raise ValueError(f"'{pid}' has no number called {name!r}")
    got = [(c["name"], *_to_script(entries[c["name"]], c["value"], c.get("unit"))) for c in changes]
    got = [g for g in got if abs(g[1] - float(entries[g[0]]["value"])) > 1e-6]      # the same number written otherwise (#171)
    if not got:
        return {"version": store.design.part(pid).version, "said": "nothing to change", "value": None, "notes": [],
                "moved": False, "read": True, "report": None, "failed": {}, "warning": None}
    notes = [n for *_, ns in got for n in ns]
    values = {name: mm for name, mm, _, _ in got}
    said_each = [f"{name} to {s}" for name, _, s, _ in got]
    joined = said_each[0] if len(said_each) == 1 else ", ".join(said_each[:-1]) + " and " + said_each[-1]
    said = f"set {joined} by hand"
    script = store.read_script(pid)
    new = aero.set_params(script, values)            # the rewrite the skeleton's drive makes too (#143)
    # built first, from its own PARAMS (builds never override, #143): a value it won't build with isn't written
    built = sandbox.run_script(new, {})
    if not built.ok:
        tail = [ln for ln in (built.feedback or "").strip().splitlines() if ln.strip()]
        why = re.sub(r"^[A-Za-z_.]*(?:Error|Exception):\s*", "", tail[-1].strip()) if tail else "the build failed"
        raise ValueError(f"it won't build with {', '.join(said_each)}: {why}")
    try:
        was = store.part_geometry(pid)
        before = _shape(was)
    except Exception:  # noqa: BLE001 — a part that didn't build before: whether it moved isn't known
        was, before = None, None
    version = store.write_part(pid, new, action="params", feedback=said,
                               extra={"params": {n: [entries[n]["value"], round(mm, 3)] for n, mm in values.items()}},
                               built=(new, {}, built.geometry))      # its trial build is this version's (#97)
    from . import follows

    followed = follows.said(store)                   # the parts that read these numbers moved with them (#266)
    if followed:
        said = f"{said}; {followed}"
    after = _shape(store.part_geometry(pid))
    report, errors = store.evaluate(tolerant=True)
    moved = before is None or after != before
    if moved and len(values) == 1:                   # a partial clamp, where the measurement can only be this number's (#107)
        name, mm = next(iter(values.items()))
        if entries[name]["read"] and entries[name]["unit"] == "mm":
            probe = _probe(name, mm, built.geometry, was)
            if probe:
                notes.append(probe)
    if load_study.list_runs(store, pid):           # its strength check is of the older shape now (#147 review)
        label = getattr(store.design.part(pid), "label", None)
        notes.append(f"strength: check {'the ' + label if label else 'this part'} again")
    return {"version": version, "said": said, "value": round(got[-1][1], 3), "notes": notes, "moved": moved,
            "read": all(entries[n]["read"] for n in values), "report": report, "failed": errors or {},
            "warning": _ignored(entries, values, got, moved)}


def _ignored(entries: dict, values: dict, got: list, moved: bool) -> Optional[str]:
    """A value the build ignores or clamps, said (#107): those its build never reads, or, if nothing moved, the rest."""
    unread = [n for n in values if not entries[n]["read"]]
    if unread:
        return (f"{' and '.join(unread)} {'is' if len(unread) == 1 else 'are'}n't used by the part's build, so setting "
                f"{'it' if len(unread) == 1 else 'them'} changed nothing")
    if not moved:
        each = " and ".join(f"{n} at {s}" for n, _, s, _ in got)
        return f"the part's shape didn't change: its build clamps or ignores {each}"
    return None


def set_value(store: DesignStore, pid: str, name: str, value: float, unit: Optional[str] = None) -> dict:
    """Set one number by hand: :func:`set_values` with one change."""
    return set_values(store, pid, [{"name": name, "value": value, "unit": unit}])
