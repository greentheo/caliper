### 2026-06-12 · CALI-22 · Author-loop fit & refine — edit the real part, not a bracket
- **Why now:** the fit bug Theo hit — fit/refine rebuilt via the bracket generator, so they ignored an
  authored `part.py` (CALI-19 guarded them to *fail honestly*). Now they **edit the real part**: route
  through `improve()` **seeded with the existing script**, so the LLM revises `part.py` to clear a
  reference or apply a plain-language change — the front edge of CALI-21 (insert-into-assembly).
- **`authoring.improve(..., seed_script, seed_feedback, ref_base)`:** primes round 1 with an existing
  part + the new constraint, so the model revises rather than starting over. Same build-error +
  failing-measurement healing as `gen`.
- **`refit_authored(spec, script, …)`** — spec already carries the reference + fit assertion(s) (via
  `fit.attach_reference`); seeds the loop with `part.py` and feeds the fit checks. **`refine_authored(
  spec, script, instruction, …)`** — folds the instruction into `spec.intent` (so a later round can't
  quietly undo it) and seeds the loop.
- **CLI:** `caliper fit <authored-run> --fit slip` and `caliper refine <authored-run> "…"` now route
  through the author loop (no more "refuse authored" return-2). **Webapp:** `/api/fit` + `/api/refine`
  do the same (the 422 guards are gone); a shared `_finish_authored()` persists script+STL+refs.
  `/api/gen` refactored onto it too.
- Tests: `improve` seed-priming; `refit_authored` drives a 60→30 mm box to clear a reference (2 rounds,
  fed the failing `interference`); `refine_authored` intent-fold; CLI fit+refine route-through; server
  `/api/fit` + `/api/refine` route-through (replacing the old 422 guards). **138 passed.**
- **Live (LLM) path** needs `ANTHROPIC_API_KEY`; the routing is verified deterministically via injected
  authors. Webapp/CLI live runs are Theo's to drive.
  Commit: 72b0df4
