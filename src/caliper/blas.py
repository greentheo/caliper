"""CALI-208: BLAS on one thread, on every thread that solves.

``import caliper`` sets the thread counts before numpy loads, and every thread then runs BLAS on one. Where numpy loaded
first, an OpenMP OpenBLAS takes each thread's count from that thread: holding the importing thread doesn't hold a thread
started later, which runs at libomp's default (caliper-reviewer, on #350: 13 of 27 solves at once wrong, reported as
converged). So the job pools hold each of their threads, and the strength check's solve holds the one it runs on."""

import functools
import threading
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


@functools.lru_cache(maxsize=None)
def fresh_single() -> bool:
    """Whether a thread started now runs BLAS on one thread: libomp's default, read when numpy loaded. One where Caliper
    loaded first; the shell's where numpy did. Without threadpoolctl it can't be told, so no (#346)."""
    try:
        from threadpoolctl import threadpool_info
    except ImportError:  # pragma: no cover
        return False
    out: list[bool] = []
    t = threading.Thread(target=lambda: out.append(all(int(p.get("num_threads", 1)) == 1 for p in threadpool_info())))
    t.start()
    t.join()
    return out[0]


def cases_safe() -> None:
    """whittle's ``solve_each`` (greentheo/whittle#9) runs a check's cases on threads it starts, where the calling
    thread's BLAS is on one thread. A thread it starts takes the process's default, not the caller's: where that isn't
    one (numpy loaded before Caliper), solves at once can come back wrong. So there its cases go one at a time
    (``CASE_THREADS = 1``), for the process: the default can't change. #352 has whittle holding its own threads."""
    if fresh_single():
        return
    try:
        from whittle.physics import fea
    except ImportError:  # pragma: no cover
        return
    if hasattr(fea, "CASE_THREADS"):
        fea.CASE_THREADS = 1
