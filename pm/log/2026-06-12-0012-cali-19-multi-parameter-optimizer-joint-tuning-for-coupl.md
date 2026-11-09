### 2026-06-12 · CALI-19b · Multi-parameter optimizer — joint tuning for coupled fits
- **Why now:** CALI-19's tuner is **1-D** (one knob per failing check). Assembly fits *couple*: one
  clearance depends on two dimensions, or two mates fight over the same wall. Tuning one knob at a time
  stalls at a saddle the per-axis sweeps can't leave. The assembly spine needs joint N-D tuning.
- **`decide.tune_multi(spec, params, eval_fn, engine="coord")`:** searches the joint continuous space
  against a **global** objective — maximize `(all_pass, #passing, worst signed margin, −total
  normalized change)`. Worst-margin drives every assertion toward/over its threshold at once;
  change-from-init keeps the solution snug.
- **Engine = coordinate descent by default** — deterministic and *eval-frugal* (geometry rebuilds are
  the expensive thing): sweep each knob over a coarse grid + a refined local window against the global
  score, until a sweep stops improving. **Escalates to a global `scipy.optimize.differential_evolution`
  (seeded, deterministic) ONLY if coordinate descent can't reach feasibility** — i.e. the genuinely
  coupled case CD traps on. Cheap-first keeps separable problems off the expensive path.
- **`decide` route 0 (CALI-19b):** with ≥2 continuous knobs and a failing numeric check, tune the whole
  vector jointly; taken only if it improves (more passing / all-pass), else fall through to the 1-D +
  snug path. Single-knob specs are untouched — the common case stays 1-D.
- Tests: a deliberately **coupled** 2-knob problem (gap band on `W+D` + budget on `W*D`, feasible only
  asymmetric) — coordinate descent escalates to scipy and solves it; `engine="scipy"` solves it
  directly; a **separable** 2-knob problem is solved by CD alone (scipy spy asserts it's never called);
  `decide` routes coupled failures to the multi move. **142 passed.**
  Commit: a84397b
