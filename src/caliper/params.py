"""CALI-108 (#108, the backend) — a part's exact numbers, set by hand, with no Claude call.

Theo, driving the bar stool: "the advantage to manual cad is the ability to specify things precisely". A part's script
keeps its dimensions in ``PARAMS`` (mm, the scripts' unit), with bounds in ``RANGES``, and ``build(params)`` merges
overrides. So an exact number needs no designer: :func:`listing` says each one in plain words (its comment), and
:func:`set_value` sets one. It converts the person's unit to mm, refuses a value outside its range (saying the range),
builds the part with it first, then rewrites only that ``PARAMS`` value (``aero.write_params``: by its source position,
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


def unit_of(name: str, note: str) -> str:
    """A number's unit, as the person reads it: "deg" for an angle, "" for a count, else "mm" (the scripts' unit)."""
    text = f"{name} {note}".lower()
    if re.search(r"\bdeg|degree|angle|°", text):
        return "deg"
    if re.search(r"^n_|_count\b|\bcount\b|number of|\bhow many\b", text):
        return ""
    return "mm"


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


def set_value(store: DesignStore, pid: str, name: str, value: float, unit: str = "mm") -> dict:
    """Set one ``PARAMS`` entry by hand: no Claude call. Returns ``{version, said, value, moved, report, failed}``;
    raises ValueError, saying why, for a name it doesn't have, a unit it can't read, a value outside its range, or a
    value the part won't build with (nothing written then)."""
    from . import sandbox
    from .assembly import skeleton_params
    from .plan import skeleton_values

    entries = {e["name"]: e for e in listing(store, pid)}
    if name not in entries:
        raise ValueError(f"'{pid}' has no number called {name!r}")
    e = entries[name]
    if e["unit"] == "mm":
        if unit not in TO_MM:
            raise ValueError(f"{name} is a length: give it in mm or in, not {unit!r}")
        mm = float(value) * TO_MM[unit]
    else:
        mm = float(value)
    lo_hi = e["range"]
    if lo_hi and not (lo_hi[0] - 1e-9 <= mm <= lo_hi[1] + 1e-9):
        unit_said = e["unit"] or ""
        raise ValueError(f"{name} must be between {lo_hi[0]:g} and {lo_hi[1]:g} {unit_said}".rstrip()
                         + f": {_said(float(value), unit) if e['unit'] == 'mm' else f'{mm:g}'} is outside it")
    script = store.read_script(pid)
    new = aero.write_params(script, {name: mm}, keep_float=True)
    # built first, through the override path (the skeleton's numbers too): a value it won't build with isn't written
    over = skeleton_params(new, skeleton_values(store.design.skeleton or []))
    built = sandbox.run_script(new, over)
    if not built.ok:
        tail = [ln for ln in (built.feedback or "").strip().splitlines() if ln.strip()]
        raise ValueError(f"it won't build with {name} at {_said(float(value), unit)}: "
                         f"{tail[-1].strip() if tail else 'the build failed'}")
    try:
        before = _shape(store.part_geometry(pid))
    except Exception:  # noqa: BLE001 — a part that didn't build before: whether it moved isn't known
        before = None
    said = _said(float(value), unit) if e["unit"] == "mm" else f"{mm:g} {e['unit']}".strip()
    version = store.write_part(pid, new, action="params", feedback=f"set {name} to {said} by hand",
                               extra={"params": {name: [e["value"], round(mm, 3)]}})
    after = _shape(store.part_geometry(pid))
    report, errors = store.evaluate(tolerant=True)
    moved = before is None or after != before
    return {"version": version, "said": f"set {name} to {said} by hand", "value": round(mm, 3),
            "moved": moved, "read": e["read"], "report": report, "failed": errors or {},
            # a value the build ignores or clamps, said (#107)
            "warning": (None if moved and e["read"] else
                        f"{name} isn't used by the part's build, so setting it changed nothing" if not e["read"] else
                        f"the part's shape didn't change: its build clamps or ignores {name} at {said}")}
