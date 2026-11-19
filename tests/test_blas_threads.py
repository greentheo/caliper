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
