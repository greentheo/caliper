### 2026-11-19 · CALI-208 (#347) · round two: BLAS on one thread on every thread that solves

caliper-reviewer, on #350 at aad57d9, reproduced the bug on main through the strength check's own solve. Of 27 solves at
once, 14 came back wrong, up to 2,384× off, and 11 of those reported converged. At aad57d9, every real entry read right
(0 of 27). But my claim that "threadpoolctl holds it where numpy loaded first" was wrong.
- This env's OpenBLAS is the OpenMP build. It takes its thread count from the calling thread.
- `threadpool_limits(1)` at import holds the importing thread only. A thread started later runs at libomp's default, 12.
- With numpy imported first, 13 of 27 solves came back wrong.
- My test read the pools from the main thread, so it passed. **The test was wrong, and the claim with it.**

**The fix** (`caliper/blas.py`):
- `one_thread()` is a `with` that holds this thread's pools at one and restores them after. `hold()` holds them for
  good, as a thread pool's initializer.
- **The job pools** (`JobRunner`'s job and study pools) start each thread with `hold`. Everything the app runs is held,
  whatever loaded first.
- **The strength check's solve** is now `load_study.solve(ls, solid)`, which runs whittle's solve inside `one_thread()`.
  `check_load` (and so carve, pictures, Lighten's cuts and coupons) and Lighten's filled solve go through it. A
  notebook's or script's own thread is held at the solve.
- The package comment no longer claims numpy-first is covered by the import; it says where it's held.

**Pinned** (`tests/test_blas_threads.py`, two more tests):
- in a fresh process with numpy and scipy imported first, the pools read 1 on a job-pool thread, on a study-pool thread,
  and inside the strength check's solve on a plain thread. An unheld plain thread reads more than 1, so the probe can
  tell.
- a guard: `.solver().solve(` appears in Caliper's source once, inside `load_study.solve`, so a new solve site must go
  through the hold.

**Fail first:** both failed at aad57d9. A job thread read openmp 12; Lighten called the solver directly.

**Mutants** (each anchor once, scratch copy), all 6 caught:
1. the solve not held;
2. the job pool's initializer dropped;
3. the study pool's initializer dropped;
4. Lighten's solve calling the solver directly (the guard);
5. `hold` a no-op;
6. `one_thread` a no-op.

**Not covered:** whittle's own studies called outside a job thread (frame, aero's ParametricStudy) in a process that
loaded numpy first. In the app they run on held job threads. **Not re-measured:** the reviewer's 27-solve hammer at this
head; their row "each solve in `threadpool_limits(1)`: 0 of 27" is what this does.
