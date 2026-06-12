"""CALI-16 — run an LLM-authored CadQuery script safely, in a subprocess.

The generator's primary strategy (design spec §2) is an LLM-authored parametric script. We can't
trust authored code to be well-behaved (infinite loops, kernel hangs, exceptions), so it runs in a
**separate process** with a timeout; the parent stays alive and turns any failure into structured
feedback (the "stack trace" channel) for the author loop (CALI-16) and, later, the structural-edit
loop (CALI-17).

Security posture is **local-trust**: this is a single user running it on their own machine with their
own key, so the threat model is "the LLM writes runaway/buggy code", not a malicious attacker. A hard
sandbox (container / seccomp / network cutoff) is Phase-2 hardening — noted, not built.

The subprocess exports **STEP** (keeps the B-rep), which the parent re-imports into a
:class:`~caliper.measure.Geometry`, so the exact hole/face probes still work on authored parts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RunResult:
    """Outcome of executing one authored script. ``geometry`` is None unless ``ok``."""

    ok: bool
    geometry: Any = None        # caliper.measure.Geometry on success
    step_path: Optional[str] = None
    error: str = ""
    traceback: str = ""

    @property
    def feedback(self) -> str:
        """The compact failure text to hand back to the author for a retry."""
        return (self.traceback or self.error).strip()


def run_script(
    script: str,
    params: Optional[dict] = None,
    timeout: float = 25.0,
    workdir: Optional[str] = None,
) -> RunResult:
    """Execute ``script`` (which must define ``build(params)``) in a subprocess; load the result.

    Returns a :class:`RunResult` with a :class:`~caliper.measure.Geometry` on success, or a structured
    error + traceback on failure (build exception, bad contract, timeout, or a crash that left no STEP).
    """
    params = params or {}
    tmp = workdir or tempfile.mkdtemp(prefix="caliper_sandbox_")
    in_path = os.path.join(tmp, "in.json")
    step_path = os.path.join(tmp, "part.step")
    status_path = os.path.join(tmp, "status.json")
    with open(in_path, "w") as f:
        json.dump({"script": script, "params": params}, f)

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "caliper._sandbox_runner", in_path, step_path, status_path],
            capture_output=True, text=True, timeout=timeout, cwd=tmp,
        )
    except subprocess.TimeoutExpired:
        return RunResult(ok=False, error=f"sandbox timed out after {timeout:g}s "
                                         "(the authored script took too long or hung)")

    # the runner writes a status file so we don't have to scrape OCCT-chatty stdout
    if os.path.isfile(status_path):
        try:
            status = json.load(open(status_path))
        except Exception:
            status = {"ok": False, "error": "sandbox produced an unreadable status", "traceback": ""}
    else:
        status = {
            "ok": False,
            "error": f"sandbox crashed (exit {proc.returncode}) with no status",
            "traceback": (proc.stderr or "").strip()[-4000:],
        }

    if not status.get("ok"):
        return RunResult(ok=False, error=status.get("error", "unknown sandbox error"),
                         traceback=status.get("traceback", ""))
    if not os.path.isfile(step_path):
        return RunResult(ok=False, error="sandbox reported success but exported no STEP file")

    # re-import the B-rep in the parent → full measurement (mesh + exact feature probes)
    try:
        import cadquery as cq

        from .measure import Geometry

        wp = cq.importers.importStep(step_path)
        geom = Geometry.from_cadquery(wp)
        geom.require_mesh()  # surface tessellation errors here, not later in sensing
    except Exception as e:  # noqa: BLE001
        import traceback as _tb

        return RunResult(ok=False, error=f"could not import the authored STEP: {e}",
                         traceback=_tb.format_exc())
    return RunResult(ok=True, geometry=geom, step_path=step_path)
