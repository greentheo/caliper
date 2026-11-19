"""CALI-208: BLAS on one thread, on every thread that solves.

``import caliper`` sets the thread counts before numpy loads, and every thread then runs BLAS on one. Where numpy loaded
first, an OpenMP OpenBLAS takes each thread's count from that thread: holding the importing thread doesn't hold a thread
started later, which runs at libomp's default (caliper-reviewer, on #350: 13 of 27 solves at once wrong, reported as
converged). So the job pools hold each of their threads, and the strength check's solve holds the one it runs on."""

from contextlib import AbstractContextManager, nullcontext
from typing import Any


def one_thread() -> AbstractContextManager[Any]:
    """This thread's BLAS and OpenMP pools at one thread, as a ``with``; restored after. A no-op without threadpoolctl
    (not a dependency; the environment ``import caliper`` sets is the pin then)."""
    try:
        from threadpoolctl import threadpool_limits
    except ImportError:  # pragma: no cover
        return nullcontext()
    return threadpool_limits(limits=1)


def hold() -> None:
    """This thread's pools at one thread, for good: a thread pool's initializer."""
    one_thread()                       # threadpoolctl applies the limit as it's made; never leaving it, it stays
