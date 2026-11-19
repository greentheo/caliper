"""CALI-208: every entry that solves runs its BLAS on one thread.

With this OpenMP OpenBLAS, two solves at once in one process come back wrong while saying they converged (reviewer-2,
on whittle#9: a residual of about 0.6 against an rtol of 1e-5, a stress off by up to 39%, already so at 25e282e). The
served app runs a study per request in threads, so two studies at once could silently mis-solve. Only CI pinned the
threads (CALI-114). Now ``import caliper`` pins them before numpy loads, so the app, the CLI and the workers all run
single-threaded BLAS, whatever the shell says.

Each entry is imported fresh, in its own process, with the shell asking for more threads."""

import json
import os
import subprocess
import sys

import pytest

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
PROBE = """
import json, os, sys
import {entry}
out = {{k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}}
try:
    from threadpoolctl import threadpool_info
    out["pools"] = sorted({{i["internal_api"]: i["num_threads"] for i in threadpool_info()}}.items())
except ImportError:
    out["pools"] = None
print(json.dumps(out))
"""


@pytest.mark.parametrize("entry", ["caliper", "caliper.cli", "caliper.server", "caliper._build_worker",
                                   "caliper._sandbox_runner",
                                   "numpy, scipy.sparse.linalg, caliper"])   # numpy loaded first: its pools held to one
@pytest.mark.parametrize("asked", [None, "8"])
def test_every_entry_runs_blas_on_one_thread(entry, asked):
    env = {k: v for k, v in os.environ.items() if k not in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                                              "MKL_NUM_THREADS", "PYTHONPATH")}
    env["PYTHONPATH"] = os.path.abspath(SRC)
    if asked:
        env.update(OMP_NUM_THREADS=asked, OPENBLAS_NUM_THREADS=asked)
    r = subprocess.run([sys.executable, "-c", PROBE.format(entry=entry)], env=env, capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    got = json.loads(r.stdout.strip().splitlines()[-1])
    assert (got["OMP_NUM_THREADS"], got["OPENBLAS_NUM_THREADS"], got["MKL_NUM_THREADS"]) == ("1", "1", "1")
    if got["pools"] is not None:                             # the libraries loaded, as they'll run
        assert all(n == 1 for _, n in got["pools"]), got["pools"]


#: numpy and scipy loaded before Caliper, then the pools read from threads that aren't the main one: the job pools'
#: threads, and a plain thread that runs the strength check's solve (caliper-reviewer, on #350: a thread started after
#: numpy loaded runs OpenMP at libomp's default, 12 here, whatever the main thread was held to; 13 of 27 solves wrong).
THREADED = """
import json, threading
import numpy, scipy.sparse.linalg
import caliper
from threadpoolctl import threadpool_info
from caliper import load_study as L
from caliper.jobs import JobRunner

def pools():
    return sorted({i["internal_api"]: i["num_threads"] for i in threadpool_info()}.items())

out = {}
r = JobRunner(workers=1, study_workers=1)
out["job"] = r._pool.submit(pools).result()
out["study"] = r._studies.submit(pools).result()

class Solver:
    def solve(self, solid):
        out["solve"] = pools()
        return type("R", (), {"supported": False})()

class LS:
    solid = None
    def load(self, force, box=None):
        pass
    def solver(self):
        return Solver()

ctx = {"ls": LS(), "loads": [{"name": "n", "lb": 1, "factor": 1.0, "force": (0.0, 0.0, -1.0), "lo": 0, "hi": 0}],
       "boxes": [None], "mat": {}}
t = threading.Thread(target=L.check_load, args=(ctx, 0, 2.0))
t.start(); t.join()
t = threading.Thread(target=lambda: out.__setitem__("bare", pools()))   # a thread nothing holds: the control
t.start(); t.join()
print(json.dumps(out))
"""


def test_threads_run_blas_on_one_thread_where_numpy_loaded_first():
    pytest.importorskip("threadpoolctl")
    env = {k: v for k, v in os.environ.items() if k not in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                                              "MKL_NUM_THREADS", "PYTHONPATH")}
    env["PYTHONPATH"] = os.path.abspath(SRC)
    r = subprocess.run([sys.executable, "-c", THREADED], env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    got = json.loads(r.stdout.strip().splitlines()[-1])
    for where in ("job", "study", "solve"):
        assert got[where] and all(n == 1 for _, n in got[where]), (where, got[where])
    assert any(n > 1 for _, n in got["bare"]) or os.cpu_count() == 1   # an unheld thread reads more: the probe can tell


def test_every_solve_in_caliper_goes_through_the_hold():
    """A new solve site must be held too: the strength check's ``solve`` is the one place that calls whittle's."""
    import re

    root = os.path.join(SRC, "caliper")
    calls = []
    for name in sorted(os.listdir(root)):
        if name.endswith(".py"):
            text = open(os.path.join(root, name)).read()
            calls += [name for m in re.finditer(r"\b(\w+)(?:\(\))?\.solve\(", text)
                      if m.group(1) not in ("linalg", "L")]       # numpy's isn't whittle's; L.solve is the hold
    assert calls == ["load_study.py"], calls
