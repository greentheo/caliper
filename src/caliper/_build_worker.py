"""CALI-39 — a warm subprocess that builds one authored script over and over.

Run as: ``python -m caliper._build_worker <response-fd> <tolerance> <angular>`` with the script on the
first stdin line (JSON ``{"script": ...}``) and one JSON params dict per following line.

A parametric drag search calls the part's ``build(params)`` a thousand-odd times. The one-shot sandbox
(:mod:`caliper._sandbox_runner`) pays a fresh process and a CadQuery import — 1–2 s — every call; this
pays it once. Same isolation as the sandbox (a separate process the parent can kill on a timeout), same
contract (``build(params)`` returns a CadQuery Workplane/Shape), but each answer is the tessellation:
a JSON header line, then the vertices as float64 and the triangles as int64, raw.

Answers go to a dedicated pipe (``response-fd``), not stdout, because OCCT writes to stdout at the C
level and would corrupt the stream.
"""

from __future__ import annotations

import json
import os
import struct
import sys
import traceback


def _shape_of(result, cq):
    """A single Shape from whatever ``build`` returned (Workplane, Shape, or a Workplane of several)."""
    if isinstance(result, cq.Workplane):
        shapes = [v for v in result.vals() if isinstance(v, cq.Shape)]
        if not shapes:
            raise ValueError("build(params) returned a Workplane with no solid on it")
        return shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)
    if isinstance(result, cq.Shape):
        return result
    raise ValueError(f"build(params) returned {type(result).__name__}, not a CadQuery Workplane/Shape")


def main() -> int:
    out = os.fdopen(int(sys.argv[1]), "wb", buffering=0)
    tolerance, angular = float(sys.argv[2]), float(sys.argv[3])

    def reply(header: dict, payload: bytes = b"") -> None:
        line = json.dumps(header).encode() + b"\n"
        out.write(struct.pack("<I", len(line)) + line + payload)

    try:
        import cadquery as cq
        import numpy as np

        script = json.loads(sys.stdin.readline())["script"]
        ns: dict = {"cq": cq}
        exec(compile(script, "<authored_part>", "exec"), ns)  # noqa: S102 — sandboxed subprocess
        builder = ns.get("build")
        if not callable(builder):
            raise ValueError("script must define a function build(params)")
        reply({"ok": True, "ready": True})
    except Exception as e:  # noqa: BLE001 — a script that won't even load is the first answer
        reply({"ok": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()})
        return 0

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            params = json.loads(line)
            shape = _shape_of(builder(params), cq)
            verts, tris = shape.tessellate(tolerance, angular)
            v = np.asarray([p.toTuple() for p in verts], dtype="<f8").reshape(-1, 3)
            f = np.asarray(tris, dtype="<i8").reshape(-1, 3)
            reply({"ok": True, "nv": len(v), "nf": len(f)}, v.tobytes() + f.tobytes())
        except Exception as e:  # noqa: BLE001 — a failed candidate is an answer, not a crash
            reply({"ok": False, "error": f"{type(e).__name__}: {e}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
