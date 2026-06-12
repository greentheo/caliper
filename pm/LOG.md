# Caliper work log

Append-only. Newest first. One entry per shipped task or notable decision.
Format: `### YYYY-MM-DD · CALI-N · title` then what changed, tests, and the commit hash.

---

### 2026-06-11 · CALI-1, CALI-3, CALI-5 · spec schema, evaluator, intake (verified)
- **CALI-1** spec schema: pydantic models (continuous/discrete/fixed params, references, machine stub,
  assertions under the `assert` alias); lossless YAML/JSON round-trip; validation on bad input.
- **CALI-3** evaluator: safe AST interpreter (no `eval`), signed margins for comparisons, compound
  `and` reports the binding margin, deferred probes (e.g. `interference`) marked `deferred` not failed.
- **CALI-5** intake: deterministic offline drafting for the bracket family (parses size, hole spec,
  extrusion width, cable), ask-don't-assume clarify gate, LLM path with offline fallback.
- Tests: **29 passed, 3 skipped** (CadQuery-only tests await the OCCT env) in a throwaway venv.
- Added `rtree` dependency (trimesh ray casting needs it for `min_wall_thickness`).
- Commit: _pending_

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
- Commit: _pending_

### 2026-06-11 · CALI-2, CALI-4 · measurement + generator (in progress)
- **CALI-2** measurement API written; mesh side verified (bbox, volume, mass, watertight, body_count,
  ray-cast `min_wall_thickness`, deferred probes). B-rep hole detection awaits the OCCT env.
- **CALI-4** corner-bracket CadQuery generator written (L-profile extrude, per-leg bolt holes, optional
  ribs + cable bore, structured build-error capture). Awaits the OCCT env to verify.
- Commit: _pending_

---

### 2026-06-11 · CALI-0 · Project scaffolding
- Initialized local git repo. Created `src/caliper/` package layout, `tests/`, `pm/`, `nightshift/`.
- Conda env `caliper` from `environment.yml` (CadQuery/OCCT + trimesh + manifold3d + scipy + pydantic).
- Stood up the .md PM system: `BOARD.md`, `TASKS.md`, `LOG.md`, `pm/README.md`.
- Adopted ai-night-shift conventions locally (loop/review/test guard) without cron — see `nightshift/`.
- Decisions: conda for the env; nightshift conventions-only (no autonomous cron yet); start M0 core this session.
- Commit: _pending_
