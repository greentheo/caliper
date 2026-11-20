"""Caliper — spec-driven, measurement-grounded generation of manufacturable 3D parts."""

import os as _os

# CALI-208: BLAS on one thread, set before anything here imports numpy. With an OpenMP OpenBLAS, two solves at once in one
# process (the served app runs a study per request in a thread) come back wrong while saying they converged: a residual
# of about 0.6 against an rtol of 1e-5, a stress off by up to 39% (reviewer-2, on whittle#9). Single-threaded, they're
# right, and faster: the FEA's sparse solves are too small to gain from threads. Only CI pinned it before (CALI-114).
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ[_k] = "1"
# Where numpy was loaded before Caliper was, this holds this thread's pools only: a thread started later runs at
# libomp's default. The job pools and the strength check's solve hold their own threads (caliper.blas).
try:
    from threadpoolctl import threadpool_limits as _limits

    _limits(limits=1)
except ImportError:     # pragma: no cover — threadpoolctl isn't a dependency; the environment above is the pin
    pass

from .assembly import Assembly, Mate, Part  # noqa: E402
from .spec import (
    Spec,
    Parameter,
    ContinuousParam,
    DiscreteParam,
    FixedParam,
    Reference,
    Assertion,
)

__all__ = [
    "Spec",
    "Parameter",
    "ContinuousParam",
    "DiscreteParam",
    "FixedParam",
    "Reference",
    "Assertion",
    "Assembly",
    "Part",
    "Mate",
]

__version__ = "0.0.1"
