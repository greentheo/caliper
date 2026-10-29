"""CALI-16 — the subprocess entry point that executes one LLM-authored CadQuery script.

Run as: ``python -m caliper._sandbox_runner <in.json> <out.step> <status.json>``

``in.json`` carries ``{"script": <source>, "params": {...}}``. We exec the script, call its
``build(params)`` function, and export the result to STEP (which preserves the B-rep, so the parent's
hole/face probes keep working). All outcomes — success, a build exception, a bad contract — are
written to ``status.json`` as ``{ok, error, traceback}`` so the parent never has to scrape stdout
(OCCT is chatty). This runs in a separate process so a runaway/buggy script can be killed on timeout.

A part that also declares what it's built from (``construction()``, ``members()``) has those read here
too, from the same run, into ``status["declared"]`` — so the parent can check them against the solid
(CALI-54) without running the script a second time.
"""

from __future__ import annotations

import inspect
import json
import sys
import traceback

#: What a part may declare beyond its shape, and checked against it (caliper.consistency).
DECLARED = ("construction", "members")


def _declared(ns: dict, params: dict) -> dict:
    """The part's declarations at these params, or ``{"error": ...}`` if one raises."""
    out = {}
    for name in DECLARED:
        f = ns.get(name)
        if not callable(f):
            continue
        try:
            out[name] = f(params, None) if len(inspect.signature(f).parameters) > 1 else f(params)
        except Exception as e:  # noqa: BLE001 — a broken declaration is feedback, not a crash
            return {"error": f"{name}() raised {type(e).__name__}: {e}"}
    return out


def _plain(o):
    """JSON for what a declaration returns: tuples are lists already; numpy numbers and arrays aren't."""
    if hasattr(o, "tolist"):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return list(o)
    return float(o)


def main() -> int:
    in_path, step_path, status_path = sys.argv[1], sys.argv[2], sys.argv[3]

    def _write(status: dict) -> None:
        try:
            text = json.dumps(status, default=_plain)
        except (TypeError, ValueError) as e:     # a declaration returned something that isn't data
            text = json.dumps({**status, "declared": {"error": f"a declaration returned something that "
                                                               f"isn't plain data: {e}"}})
        with open(status_path, "w") as f:
            f.write(text)

    try:
        data = json.load(open(in_path))
        script, params = data["script"], data.get("params", {})
    except Exception as e:  # noqa: BLE001
        _write({"ok": False, "error": f"could not read sandbox input: {e}", "traceback": ""})
        return 0

    try:
        import cadquery as cq  # noqa: F401 — available to the authored script via the namespace

        ns: dict = {"cq": cq}
        exec(compile(script, "<authored_part>", "exec"), ns)  # noqa: S102 — sandboxed subprocess
        builder = ns.get("build")
        if not callable(builder):
            raise ValueError("script must define a function build(params) -> cadquery Workplane/Solid")
        result = builder(params)
        if result is None:
            raise ValueError("build(params) returned None — it must return a cadquery Workplane/Solid")
        cq.exporters.export(result, step_path)
        _write({"ok": True, "error": "", "traceback": "", "declared": _declared(ns, params)})
    except Exception as e:  # noqa: BLE001 — build errors are first-class feedback for the author loop
        _write({"ok": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
