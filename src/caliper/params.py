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


def unit_of(name: str, note: str) -> str:
    """What a number is, as the script says it: "deg" (an angle), "count", "ratio", "mm" (a length: a length unit in
    its comment, or a length's name: wall_t, fillet_r, width, …), or "" (none of these: taken as it is)."""
    text = f"{name} {note}"
    if re.search(r"\bdeg|degree|angle|°", text, re.I):
        return "deg"
    if _COUNT.search(name) or _COUNT.search(note):
        return "count"
    if _RATIO.search(name) or (_RATIO.search(note) and not _LENGTH_UNIT.search(note)):
        return "ratio"
    if _LENGTH_UNIT.search(note) or _LENGTH_NAME.search(name) or _LENGTH_WORD.search(note):
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
    if unit == "in":
        from .answers import _len

        return _len(value * IN, True)
    return f"{value:g} {unit}".strip()


def _shape(g) -> tuple:
    m = g.require_mesh()
    return (round(float(abs(m.volume)), 1), tuple(round(float(v), 2) for v in m.bounds.ravel()))


def _probe(name: str, asked_mm: float, geometry) -> str:
    """What the built part shows of a number where it can be measured (#147 review, #107's fillet: 12.7 asked, 6.3
    built): a fillet's or a hole's radius from its solid's cylinders, a wall's thinnest measure. "" where they agree."""
    from . import measure

    try:
        solid = geometry.solid
        solid = solid.val() if hasattr(solid, "val") else solid
    except Exception:  # noqa: BLE001
        solid = None
    lname = name.lower()
    if solid is not None and ("fillet" in lname or "hole" in lname):
        from OCP.BRepAdaptor import BRepAdaptor_Surface  # type: ignore

        radii = [BRepAdaptor_Surface(f.wrapped).Cylinder().Radius() for f in solid.Faces() if f.geomType() == "CYLINDER"]
        if not radii:
            return f"its shape changed; whether its {name} is exactly {asked_mm:g} mm isn't measured"
        want = asked_mm / 2 if re.search(r"_d$|diameter|dia\b", lname) else asked_mm
        got = min(radii, key=lambda r: abs(r - want))
        if abs(got - want) > max(0.02 * want, 0.01):
            built = got * 2 if want != asked_mm else got
            return f"asked {asked_mm:g} mm, built {built:.3g} mm (the closest {'hole' if 'hole' in lname else 'fillet'})"
        return ""
    if "wall" in lname or lname.endswith("_t") or "thick" in lname:
        try:
            got = measure.min_wall_thickness(geometry)
        except Exception:  # noqa: BLE001
            return ""
        if got < asked_mm * 0.98:
            return f"its thinnest wall is {got:.3g} mm, not {asked_mm:g}: whether this {name} is exactly that isn't measured"
        return ""
    return f"its shape changed; whether its {name} is exactly {asked_mm:g} mm isn't measured"


def set_value(store: DesignStore, pid: str, name: str, value: float, unit: Optional[str] = None) -> dict:
    """Set one ``PARAMS`` entry by hand: no Claude call. Returns ``{version, said, value, moved, report, failed}``;
    raises ValueError, saying why, for a name it doesn't have, a unit it can't read, a value outside its range, or a
    value the part won't build with (nothing written then)."""
    from . import sandbox

    entries = {e["name"]: e for e in listing(store, pid)}
    if name not in entries:
        raise ValueError(f"'{pid}' has no number called {name!r}")
    e = entries[name]
    plain = name.replace("_", " ")
    notes: list[str] = []
    if e["unit"] == "mm":                         # only a length converts (#147 review)
        unit = unit or "mm"
        if unit not in TO_MM:
            raise ValueError(f"{plain} is a length: give it in mm or in, not {unit!r}")
        mm = float(value) * TO_MM[unit]
    elif e["unit"] in ("count", "ratio"):
        if unit not in (None, "", e["unit"]):
            raise ValueError(f"{plain} is a {e['unit']}: give a number, no unit")
        mm = float(value)
    elif e["unit"] == "deg":
        if unit not in (None, "", "deg"):
            raise ValueError(f"{plain} is an angle: give it in degrees")
        mm = float(value)
    else:
        mm = float(value)                         # none of these: taken as it is, said so
        notes.append(f"{name} has no unit in its script, so {mm:g} is taken as it is, not converted")
        unit = None
    lo_hi = e["range"]
    if not lo_hi:                                 # allowed, but said (#147 review)
        notes.append(f"no range is set for {name} in the script, so it isn't checked")
    if lo_hi and not (lo_hi[0] - 1e-9 <= mm <= lo_hi[1] + 1e-9):
        unit_said = e["unit"] or ""
        raise ValueError(f"{name} must be between {lo_hi[0]:g} and {lo_hi[1]:g} {unit_said}".rstrip()
                         + f": {_said(float(value), unit) if e['unit'] == 'mm' else f'{mm:g}'} is outside it")
    from . import load_study
    script = store.read_script(pid)
    new = aero.set_params(script, {name: mm})        # the rewrite the skeleton's drive makes too (#143)
    # built first, from its own PARAMS (builds never override, #143): a value it won't build with isn't written
    built = sandbox.run_script(new, {})
    if not built.ok:
        tail = [ln for ln in (built.feedback or "").strip().splitlines() if ln.strip()]
        raise ValueError(f"it won't build with {name} at {_said(float(value), unit)}: "
                         f"{tail[-1].strip() if tail else 'the build failed'}")
    try:
        before = _shape(store.part_geometry(pid))
    except Exception:  # noqa: BLE001 — a part that didn't build before: whether it moved isn't known
        before = None
    said = (_said(float(value), unit) if e["unit"] == "mm" else
             f"{mm:g} deg" if e["unit"] == "deg" else f"{mm:g}")
    version = store.write_part(pid, new, action="params", feedback=f"set {name} to {said} by hand",
                               extra={"params": {name: [e["value"], round(mm, 3)]}})
    after = _shape(store.part_geometry(pid))
    report, errors = store.evaluate(tolerant=True)
    moved = before is None or after != before
    if moved and e["read"] and e["unit"] == "mm":  # a partial clamp, against a probe where one exists (#107)
        probe = _probe(name, mm, built.geometry)
        if probe:
            notes.append(probe)
    if load_study.list_runs(store, pid):           # its strength check is of the older shape now (#147 review)
        notes.append(f"strength: check the {pid.replace('_', ' ')} again")
    return {"version": version, "said": f"set {name} to {said} by hand", "value": round(mm, 3), "notes": notes,
            "moved": moved, "read": e["read"], "report": report, "failed": errors or {},
            # a value the build ignores or clamps, said (#107)
            "warning": (None if moved and e["read"] else
                        f"{name} isn't used by the part's build, so setting it changed nothing" if not e["read"] else
                        f"the part's shape didn't change: its build clamps or ignores {name} at {said}")}
