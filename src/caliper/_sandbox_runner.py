"""CALI-16 — the subprocess entry point that executes one LLM-authored CadQuery script.

Run as: ``python -m caliper._sandbox_runner <in.json> <out.step> <status.json>``

``in.json`` carries ``{"script": <source>, "params": {...}}``. We exec the script, call its
``build(params)`` function, and export the result to STEP (which preserves the B-rep, so the parent's
hole/face probes keep working). All outcomes — success, a build exception, a bad contract — are
written to ``status.json`` as ``{ok, error, traceback}`` so the parent never has to scrape stdout
(OCCT is chatty). This runs in a separate process so a runaway/buggy script can be killed on timeout.
"""

from __future__ import annotations

import json
import sys
import traceback


def main() -> int:
    in_path, step_path, status_path = sys.argv[1], sys.argv[2], sys.argv[3]

    def _write(status: dict) -> None:
        with open(status_path, "w") as f:
            json.dump(status, f)

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
        _write({"ok": True, "error": "", "traceback": ""})
    except Exception as e:  # noqa: BLE001 — build errors are first-class feedback for the author loop
        _write({"ok": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
