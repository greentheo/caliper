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
    declared: Optional[dict] = None   # construction() / members() from the same run (CALI-54)

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

        from .occt import OCCT

        with OCCT:
            wp = cq.importers.importStep(step_path)
            geom = Geometry.from_cadquery(wp)
            geom.require_mesh()  # surface tessellation errors here, not later in sensing
    except Exception as e:  # noqa: BLE001
        import traceback as _tb

        return RunResult(ok=False, error=f"could not import the authored STEP: {e}",
                         traceback=_tb.format_exc())
    return RunResult(ok=True, geometry=geom, step_path=step_path, declared=status.get("declared") or None)


# ---------------------------------------------------------------------------
# CALI-39 — a warm worker, for a search that builds the same script a thousand times
# ---------------------------------------------------------------------------
class BuildError(RuntimeError):
    """One build failed (the script raised, timed out, or the worker died). A search skips it."""


class BuildWorker:
    """Build one authored script repeatedly in a long-lived sandboxed process.

    ``build(params)`` returns the tessellation as ``(vertices (N,3) float64, triangles (M,3) int64)``
    — what a drag model scores. The process imports CadQuery and compiles the script once; each call
    costs only the build. Isolation matches :func:`run_script`: a separate process, killed and restarted
    if a build exceeds ``timeout``. Use as a context manager so the process never outlives the search.
    """

    def __init__(self, script: str, *, timeout: float = 20.0, tolerance: float = 0.5,
                 angular: float = 0.2, startup_timeout: float = 90.0):
        self.script, self.timeout = script, timeout
        self.tolerance, self.angular, self.startup_timeout = tolerance, angular, startup_timeout
        self.proc = None
        self._rfd = None
        self.builds = self.failures = 0
        self._start()

    def __enter__(self) -> "BuildWorker":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _start(self) -> None:
        r, w = os.pipe()
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "caliper._build_worker", str(w), str(self.tolerance),
             str(self.angular)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            pass_fds=(w,),
        )
        os.close(w)
        self._rfd = r
        self._send({"script": self.script})
        header, _ = self._read(self.startup_timeout)
        if not header.get("ok"):
            self.close()
            raise BuildError(f"the script won't load: {header.get('error')}")

    def _send(self, obj: dict) -> None:
        self.proc.stdin.write(json.dumps(obj).encode() + b"\n")
        self.proc.stdin.flush()

    def _readn(self, n: int, deadline: float) -> bytes:
        import select
        import time

        buf = bytearray()
        while len(buf) < n:
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError
            ready, _, _ = select.select([self._rfd], [], [], left)
            if not ready:
                raise TimeoutError
            chunk = os.read(self._rfd, n - len(buf))
            if not chunk:
                raise BuildError("the build worker exited")
            buf += chunk
        return bytes(buf)

    def _read(self, timeout: float):
        import struct
        import time

        deadline = time.time() + timeout
        (length,) = struct.unpack("<I", self._readn(4, deadline))
        header = json.loads(self._readn(length, deadline))
        payload = b""
        if header.get("ok") and header.get("nv") is not None:
            payload = self._readn(24 * (header["nv"] + header["nf"]), deadline)
        return header, payload

    def build(self, params: dict):
        """Build with these params → ``(vertices, triangles)``; raises :class:`BuildError`."""
        import numpy as np

        if self.proc is None or self.proc.poll() is not None:
            self._restart()
        try:
            self._send({k: float(v) for k, v in params.items()})
            header, payload = self._read(self.timeout)
        except TimeoutError:
            self.failures += 1
            self._restart()
            raise BuildError(f"the build took longer than {self.timeout:g}s")
        except (BrokenPipeError, BuildError) as e:
            self.failures += 1
            self._restart()
            raise BuildError(str(e) or "the build worker died")
        if not header.get("ok"):
            self.failures += 1
            raise BuildError(header.get("error", "build failed"))
        self.builds += 1
        nv = header["nv"]
        verts = np.frombuffer(payload[: 24 * nv], dtype="<f8").reshape(-1, 3).copy()
        tris = np.frombuffer(payload[24 * nv:], dtype="<i8").reshape(-1, 3).copy()
        return verts, tris

    def _restart(self) -> None:
        self.close()
        self._start()

    def close(self) -> None:
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=5)
            except Exception:  # noqa: BLE001 — already gone
                pass
            self.proc = None
        if self._rfd is not None:
            try:
                os.close(self._rfd)
            except OSError:
                pass
            self._rfd = None
