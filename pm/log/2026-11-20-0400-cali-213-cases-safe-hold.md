### 2026-11-20 · CALI-213 (#356) · whittle's case threads made safe wherever BLAS is held

reviewer-2's should-fix on #346. `blas.cases_safe()` ran only in `load_study.solved()`. Carve's multi-case solves go
through whittle's own `solve()` and never through `solved()`. So in a process that loaded numpy before Caliper, until a
strength check had run `solved()`, whittle took the held caller as single-threaded and started case threads at
libomp's default. reviewer-2 measured 6 of 36 off serial, every one "converged".

**The fix** (`caliper/blas.py`, `caliper/__init__.py`):
- `hold()`, the initializer of every job-pool thread, calls `cases_safe()`.
- `import caliper` calls it once where numpy was already loaded, so a script that carves on its main thread is covered.
- `cases_safe()` no longer imports whittle, since `import caliper` now calls it. A whittle not yet loaded reads
  `WHITTLE_CASE_THREADS=1` when it loads; one loaded already has its `CASE_THREADS` set to 1.
- As before, all of this happens only where a freshly started thread isn't held (`fresh_single()`).

**Pinned** (`tests/test_blas_threads.py`):
- **A carve-shaped solve:** whittle's own `solve()` with two load cases, no `solved()` first, in a fresh process with
  the shell asking for 8 threads. Numpy first, where a fresh thread is unheld, it starts no case pools and
  `CASE_THREADS` is 1. Caliper first, every fresh thread is held and whittle's case pools run: the control.
  - On a BLAS whose count is the process's (CI's BLIS), a fresh thread is held either way, and the case pools are
    expected there.
- `hold()` calls `cases_safe()`.
- `cases_safe()` sets the variable for a whittle not loaded.
- A numpy-first `import caliper` loads no whittle, and sets the variable only where a fresh thread is unheld.

**Fail first:** the numpy-first carve, the hold and the variable pins failed on main. The Caliper-first control passed
there.

**Mutants** (each anchor once, scratch copy), all 4 caught:
1. `hold()` doesn't make the cases safe;
2. `import caliper` doesn't;
3. no variable for a whittle not loaded;
4. `cases_safe` imports whittle.

The fourth survived at first. My test dropped `whittle.physics.fea` from `sys.modules`, but a from-import finds it on
the still-loaded package. The test was wrong. The fresh-process pin catches it.
