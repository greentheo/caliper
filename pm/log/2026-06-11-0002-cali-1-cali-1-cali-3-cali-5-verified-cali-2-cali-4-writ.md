### 2026-06-11 · CALI-1, CALI-3, CALI-5 verified; CALI-2, CALI-4 written
- **CALI-1** spec schema: pydantic models (continuous/discrete/fixed params, references, machine stub,
  assertions under the `assert` alias); lossless YAML/JSON round-trip; validation on bad input.
- **CALI-3** evaluator: safe AST interpreter (no `eval`), signed margins for comparisons, compound
  `and` reports the binding margin, deferred probes (e.g. `interference`) marked `deferred` not failed.
- **CALI-5** intake: deterministic offline drafting for the bracket family (parses size, hole spec,
  extrusion width, cable), ask-don't-assume clarify gate, LLM path with offline fallback.
- **CALI-2** measurement API: mesh side verified (bbox, volume, mass, watertight, body_count, ray-cast
  `min_wall_thickness`, deferred probes); B-rep hole detection written, OCCT-gated.
- **CALI-4** corner-bracket CadQuery generator written (L-profile extrude, per-leg bolt holes, optional
  ribs + cable bore, structured build-error capture); OCCT-gated.
- Tests: **29 passed, 3 skipped** (CadQuery-only) in a throwaway venv. Added `rtree` dependency
  (trimesh ray casting needs it for `min_wall_thickness`).
- Commit: `0d93efa`.
