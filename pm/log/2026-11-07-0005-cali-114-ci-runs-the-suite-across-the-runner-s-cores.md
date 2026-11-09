### 2026-11-07 · CALI-114 (#116) · CI runs the suite across the runner's cores
- **`pytest-xdist`** is in the requirements. CI runs `pytest -n auto --durations=25 -m "not serial"` with
  `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `OPENBLAS_NUM_THREADS` at 1, so four FEA workers don't fight over four
  cores. A second step runs anything marked `serial` on its own (exit 5, "no tests", passes once none is).
- **Locally `pytest -rs` stays the default,** and `-n auto` is optional (TESTING.md).
- **Before,** on main: the test step took 51.5 min (646a20a) and 40.8 min (ad2f296). After: in the PR, from its CI
  runs, with `--durations=25`'s slowest tests.
- **The carve-down test is marked `serial`** (7cdc550): in parallel, with one BLAS thread, it adopted a step that
  wasn't watertight (#105, fixed by #124). After #124 merges, the mark comes off.
