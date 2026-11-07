"""CALI-107 (#107; rule 6) — a feature the person asked for either builds or the round fails, said.

On Theo's bar stool the designer wrapped a fillet and the mesh cut-outs in ``try/except`` that returned the shape
without them, and clamped the fillet's radius below what was asked; each reply said "✓ revised … Every check on this
part passes". This reads the script (it never runs it) and names each place that would hide a feature that didn't
build:

- an ``except`` (bare, or ``Exception``) whose body only passes, or hands back something unchanged (``return x``
  where ``x`` is a name the ``try`` was building on), around a CadQuery call;
- a requested size clamped below what was asked: ``min(p["x"], <something else>)``, a ``PARAMS`` value held under a
  computed limit without a word.

Each is a failed check of the round, naming the line, so the designer lets it raise with a clear message instead.
"""

from __future__ import annotations

import ast
from typing import Optional

#: The CadQuery calls that make a feature: a fallback around one of these is a feature silently skipped.
FEATURE_CALLS = {"fillet", "chamfer", "cut", "union", "intersect", "shell", "hole", "cboreHole", "cskHole",
                 "extrude", "cutBlind", "cutThruAll", "revolve", "loft", "sweep", "split", "combine", "polygon",
                 "polyline", "spline", "workplane", "translate", "rotate", "mirror", "text", "box", "cylinder",
                 "sphere", "rect", "circle", "pushPoints", "rarray", "polarArray", "edges", "faces"}
#: What a script calls its parameters: ``p = {**PARAMS, **(params or {})}`` (part_scripts.md).
PARAM_NAMES = {"p", "params", "PARAMS", "P"}


def _calls_cad(nodes) -> bool:
    for n in nodes:
        for sub in ast.walk(n):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in FEATURE_CALLS:
                return True
    return False


def _swallows(handler: ast.ExceptHandler, try_names: set) -> Optional[str]:
    """What an except handler does that hides a failure, or None."""
    # any handler type or tuple counts around a CAD call: Exception, (ValueError, RuntimeError), OCP's
    # Standard_Failure (#119 review)
    body = [b for b in handler.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
    if all(isinstance(b, (ast.Pass, ast.Continue)) for b in body):
        return "passes"
    last = body[-1] if body else None
    if isinstance(last, ast.Return) and (last.value is None or (isinstance(last.value, ast.Name)
                                                                and last.value.id in try_names | {"None"})):
        return f"returns {last.value.id if isinstance(last.value, ast.Name) else 'nothing'} unchanged"
    if isinstance(last, ast.Return) and isinstance(last.value, ast.Name):
        return f"returns {last.value.id} instead"
    root = _root(last.value) if isinstance(last, ast.Return) else None
    if root in try_names:                          # return s.translate(...): the input moved, without the feature
        return f"returns {root} without it"
    return None


def _root(node) -> Optional[str]:
    """The name a call or attribute chain starts from: ``s`` in ``s.translate((0, 0, 1)).rotate(...)``."""
    while isinstance(node, (ast.Call, ast.Attribute)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _param(node) -> Optional[str]:
    """``p["name"]`` (or ``params["name"]``): the parameter's name; else None."""
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in PARAM_NAMES
            and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
        return node.slice.value
    return None


def find(script: str) -> list[str]:
    """Each place the script would hide a requested feature, as "line N: …". [] when there's none, or when the
    script doesn't parse (the build says that)."""
    try:
        tree = ast.parse(script)
    except SyntaxError:
        return []
    out = []
    for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        args = {a.arg for a in fn.args.args}
        # a local copy of a requested size: foot_fillet_r = p["foot_fillet_r"]
        copies = {}
        for n in ast.walk(fn):
            if not isinstance(n, ast.Assign):
                continue
            for t in n.targets:
                if isinstance(t, ast.Name) and _param(n.value):
                    copies[t.id] = _param(n.value)
                elif isinstance(t, ast.Tuple) and isinstance(n.value, ast.Tuple):   # xf, d = p["x"], p["depth"]
                    for name, val in zip(t.elts, n.value.elts):
                        if isinstance(name, ast.Name) and _param(val):
                            copies[name.id] = _param(val)

        def requested(node) -> Optional[str]:
            return _param(node) or (copies.get(node.id) if isinstance(node, ast.Name) else None)
        for node in ast.walk(fn):
            if isinstance(node, ast.Try) and _calls_cad(node.body):
                used = {n.id for n in ast.walk(ast.Module(body=node.body, type_ignores=[])) if isinstance(n, ast.Name)}
                for h in node.handlers:
                    how = _swallows(h, (used | args))
                    if how:
                        out.append(f"line {h.lineno}: in {fn.name}(), an except that {how} hides a feature that "
                                   f"didn't build: let it raise, or raise with what went wrong (\"the 12.7 mm fillet "
                                   f"doesn't fit a 14 mm flange\")")
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "min"
                    and len(node.args) >= 2):
                named = [requested(a) for a in node.args]
                if any(named) and not all(named):
                    which = next(n for n in named if n)
                    out.append(f"line {node.lineno}: in {fn.name}(), min({which}, …) holds a requested size under "
                               f"a limit without saying so: if {which} doesn't fit, raise and say why")
            if (isinstance(node, ast.If) and node.body and isinstance(node.body[0], ast.Return)
                    and isinstance(node.body[0].value, ast.Name) and node.body[0].value.id in args
                    and _size_test(node.test, requested)):
                out.append(f"line {node.lineno}: in {fn.name}(), returns {node.body[0].value.id} unchanged when "
                           f"{ast.unparse(node.test)}: the feature is skipped without a word; if it can't be made, "
                           f"raise and say why")
    return sorted(set(out), key=lambda s: int(s.split(":")[0].split()[1]))


def _size_test(test, requested=lambda n: None) -> bool:
    """A comparison against a size (``actual_open_w < 6.0``), not against nothing: ``r <= 0`` and, for a requested
    parameter or its copy, ``p["holes"] < 1`` are "none asked for" (#119 review)."""
    if not isinstance(test, ast.Compare):
        return False
    sides = [test.left, *test.comparators]
    nums = [c.value for c in sides if isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
            and not isinstance(c.value, bool)]
    if not nums:
        return False
    if any(requested(c) for c in sides) and all(v in (0, 1) for v in nums):
        return False
    return any(v != 0 for v in nums)


def result(script: str):
    """The round's check: a fail naming each line, or a pass."""
    from .evaluate import AssertionResult

    found = find(script)
    return AssertionResult(id="no_silent_fallback", expr="every requested feature builds or the script says why not",
                           status="fail" if found else "pass", passed=not found, actual=len(found),
                           detail="; ".join(found))


def params(script: str) -> dict:
    """The script's PARAMS, as written (a literal dict); {} if it has none or they aren't literal."""
    try:
        tree = ast.parse(script)
    except SyntaxError:
        return {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PARAMS" for t in node.targets):
            try:
                got = ast.literal_eval(node.value)
            except ValueError:
                return {}
            return got if isinstance(got, dict) else {}
    return {}


def changed(before: str, after: str) -> list[tuple[str, object, object]]:
    """The PARAMS a revision changed: (name, before, after), in the order the new script lists them."""
    a, b = params(before), params(after)
    return [(k, a.get(k), v) for k, v in b.items() if a.get(k) != v] + [(k, v, None) for k, v in a.items() if k not in b]
