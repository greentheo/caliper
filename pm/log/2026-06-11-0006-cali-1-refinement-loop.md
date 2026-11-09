### 2026-06-11 · 🎉 M1 COMPLETE · CALI-1.M1 · refinement loop (one iteration cycle)
- New `refine.py`: a natural-language refinement → mutated spec. Offline deterministic parser for the
  common bracket edits (hole Ø, hole count, bolt spacing, wall, cable bore, ribs) plus an LLM path
  with offline fallback. Crucially mutates the *generator-read parameters* and re-syncs dependent
  assertions (e.g. a hole-Ø change updates both `hole_d` and the `bolt_pattern` assertion), so the
  change flows to the mesh, not just the acceptance text.
- Wired hole geometry into the generator: `BracketParams.from_spec` now reads `hole_d`/`hole_count`;
  intake emits them as parameters. (Backward compatible — defaults unchanged.)
- CLI: `caliper refine <run-dir|spec> "<instruction>"` loads a prior run, applies the change, re-runs
  the loop, emits a new run/STL. `_run_and_emit` shared with `run`. `make refine` target added.
- Demo: `run` → 4×Ø5.2; `refine "make the holes 8 mm"` → `bolt_pattern` re-synced to diameter=8.0,
  ALL PASS, new STL whose bytes differ (geometry changed; same triangle count). Optimizer tune
  already lived in the loop (CALI-6/7), so this completes the M1 "one NL refinement + one tune" cycle.
- Tests: **61 passed** (M1 added 14, incl. an OCCT end-to-end proving the rebuilt part has 4×Ø8 holes).
- Commits: `f78da23` (refinement loop), `cd857a4` (`make refine` target).
