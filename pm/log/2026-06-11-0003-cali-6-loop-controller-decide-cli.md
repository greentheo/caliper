### 2026-06-11 · CALI-6, CALI-7, CALI-8 · loop controller, decide, CLI
- **CALI-7** decide: continuous route (1-D grid+refine optimizer over a continuous param, scored by
  all_pass/pass-count/margin) and a structural route (bump a discrete param); defers to LLM when
  neither applies. Verified: a mass-over-budget failure is fixed by tuning `wall`.
- **CALI-6** loop controller: generate→build→sense→evaluate→decide with iteration cap, oscillation
  detection, run persistence (`runs/<id>/` spec+report+STL). Verified: converges, caps, detects
  oscillation, surfaces build failures. Injected `eval_fn` keeps it kernel-free for tests.
- **CALI-8** CLI: `caliper run "<intent>"` one-shot; `--no-llm`/`--yes` for reproducible runs; the
  ask-don't-assume clarify gate blocks non-interactive builds. Gate verified; end-to-end smoke
  (real STL) is OCCT-gated.
- Whole suite: **39 passed, 4 skipped** (CadQuery-only) in a clean venv.
- Commit: `a223b13`.
