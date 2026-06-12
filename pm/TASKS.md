# Caliper tasks (the "issues")

Acceptance criteria per task. Ids match the design spec §11 and milestones M0–M3 (§8).
Live status is on [`BOARD.md`](BOARD.md); each issue below is stamped ✅ done (with commit) or 🧊 backlog
for the record.

Priority key: **P0** = on the MVP critical path, **P1** = needed for the milestone, **P2** = nice-to-have.

---

## Milestone M0 — one-shot core (CLI, no UI)
> `intent → spec(JSON) → cadquery script → mesh → measure → report`, hardcoded to the bracket family.

### CALI-1 — Spec schema  · P0 · M0 · ✅ done (`0d93efa`)
Typed Python model + JSON/YAML (de)serialization for the spec.
**Acceptance:**
- `Parameter` with kinds `continuous` (min/max/init/unit), `discrete` (choices/init), `fixed` (value/unit).
- `Reference` (id, file, role) and a `machine` stub field (name only for now; deferred probes are no-ops).
- `Assertion` (id, expr string) and a top-level `Spec` (part, intent, parameters, references, machine, assert).
- Round-trips losslessly to/from YAML and JSON. Validates with clear errors on malformed input.
- Loads the corner-bracket worked example from the design spec §3 unchanged.
- Unit tests cover round-trip + validation failure cases.

### CALI-2 — Measurement API (MVP subset)  · P0 · M0 · ✅ done (`ff8e154`)
Implement the §8 MVP measurement subset over `trimesh` (+ CadQuery B-rep where it's cheaper/exact).
**Acceptance:**
- `bounding_box`, `volume`, `mass(density)`, `is_watertight`, `body_count` over a mesh.
- `min_wall_thickness` (ray-cast / SDF sample — documented method + known-part test).
- `holes` / `holes_matching(diameter, on, count, tol)` — start B-rep-based on CadQuery solids.
- `render_views` may be a stub returning paths (vision channel is sanity-only; **never returns a number**).
- Deferred probes (overhang, slice, fea, interference/clearance until M3) present as documented no-ops/`NotImplemented`.
- Tests assert exact values against known primitives (box, box-with-hole) within tolerance.

### CALI-3 — Evaluator  · P0 · M0 · ✅ done (`0d93efa`)
Parse each assertion `expr` and produce `{id, pass, actual, margin}`.
**Acceptance:**
- Safe expression evaluation (no arbitrary `eval`; restricted namespace of measurement results + helpers like `circle`, `holes_matching`).
- Report object: per-assertion `pass`, `actual`, `margin`, plus an overall `all_pass`.
- `margin` is signed distance to the threshold where meaningful (e.g. `bbox.dx <= 220` → `220 - dx`).
- Rich/plain text report rendering for the CLI.
- Tests: a spec + a measurement bundle → expected report.

### CALI-4 — Generator (bracket family)  · P0 · M0 · ✅ done (`ff8e154`)
CadQuery script template + LLM-authored parametrics for the corner-bracket family; capture build errors.
**Acceptance:**
- A parametric `bracket(params) -> cadquery.Workplane` template driven by spec parameters.
- `build(spec) -> {solid, mesh, build_ok, error}` — kernel errors captured as structured feedback (the "stack trace").
- Exports STL via trimesh.
- Tests build the default bracket and assert it's watertight with the expected hole count.

### CALI-5 — Intake (Claude)  · P0 · M0 · ✅ done (`0d93efa`)
`intent → draft spec`, with a clarify gate and human confirmation.
**Acceptance:**
- Claude API call: intent + machine → draft `Spec` (CALI-1 object).
- **Ask-don't-assume:** surfaces ambiguities as questions, **stops** before building until confirmed.
- Deterministic offline fallback (templated spec) so M0 runs without network in tests.
- Tests use a recorded/stubbed response; no live API call in CI.

### CALI-6 — Loop controller  · P0 · M0 · ✅ done (`a223b13`)
Wire `generate → build → sense → evaluate → decide` with an iteration cap + oscillation detection.
**Acceptance:**
- Tiered feedback: cheap checks (build, bbox, wall) before expensive (render).
- Iteration cap and simple oscillation detection (repeated identical reports → stop).
- Persists each run (spec + script + measurements + STL) under `runs/<id>/` for diffing.
- Tests: a converging case reaches `all_pass`; a non-converging case stops at the cap.

### CALI-7 — Decide (route by failure type)  · P0 · M0 · ✅ done (`a223b13`)
Continuous failures → optimizer (one param); structural failures → LLM script edit.
**Acceptance:**
- Classify each failing assertion as continuous vs structural from the involved parameters.
- Continuous path: `scipy.optimize` (or grid) tunes a single continuous parameter to satisfy the assertion.
- Structural path: Claude edits the script given the failure report (value + margin).
- Tests: a mass-over-budget failure is fixed by the optimizer tuning `wall`.

### CALI-8 — CLI (M0 end-to-end)  · P0 · M0 · ✅ done (`ff8e154`)
`caliper "<intent>"` runs the full one-shot on the bracket family and prints the report.
**Acceptance:**
- `caliper run "a 60mm corner bracket for 2020 extrusion with four M5 holes"` → spec → build → measure → report → STL path.
- `--no-llm` flag uses the offline intake fallback for deterministic demo/tests.
- Smoke test exercises the whole pipeline with `--no-llm`.

---

## Milestone M1 — one iteration cycle
### CALI-1.M1 — Refinement loop  · P1 · M1 · ✅ done (`f78da23`)
Feed the report back to decide; support one NL refinement ("make the holes bigger") and one optimizer tune. Proves the loop.
**Acceptance (met):**
- `refine.apply_refinement(spec, instruction)` → mutated spec; offline deterministic parser (hole Ø,
  hole count, bolt spacing, wall, cable bore, ribs) + LLM path with offline fallback.
- Mutates generator-read parameters AND re-syncs dependent assertions, so the change reaches the mesh.
- `caliper refine <run-dir|spec> "<instruction>"` re-runs the loop and emits a new run/STL.
- Optimizer tune reused from CALI-6/7. Tests incl. an OCCT end-to-end proving the rebuilt part changed.

---

## Milestone M2 — webapp wrapper
### CALI-9 — Webapp  · P1 · M2 · ✅ done (`3c78fff`)
FastAPI around the library + a three.js front end. The demoable "jam in 3D space" moment.
**Acceptance:**
- FastAPI app: `POST /api/run` (intent → spec/build/measure/report → run_id + STL url),
  `POST /api/refine` (run_id + instruction → re-run), `GET /api/runs/{id}/part.stl`, `GET /api/health`.
- Front end: intent box, refine box, spec view, measurement report panel (✓/✗ + margins), 3D viewer
  (three.js STL loader + orbit), STL download. MVP uses no-build vanilla three.js (ESM via import map);
  React is a later refactor — the loop is the product, the UI is a wrapper.
- **3Dconnexion SpaceMouse support** (key ask — Theo has one; standard for 3D modelling, works in
  Prusa/Fusion): drive the viewer camera via **WebHID** (`navigator.hid`) — 6DOF translate/rotate →
  pan/dolly/orbit, with a "Connect SpaceMouse" button, deadzone + sensitivity, graceful fallback to
  mouse when WebHID/hardware is absent. (WebHID needs Chrome/Edge over localhost/https.)
- `caliper serve` CLI + `make serve`. Tests: FastAPI TestClient for the endpoints (run/refine OCCT-gated).

---

## Milestone M3 — references
### CALI-10 — References  · P1 · M3 · 🧊 backlog
STL intake as `role: fixed`; add `interference` + `min_clearance` measurements and assertions; iterate a part to fit a reference. The FEA-free Stage 2 loop.

---

## Generator capabilities (from real use — backlog)
### CALI-11 — Variable bend angle  · P2 · generator · 🧊 backlog
Today the bracket is a fixed 90° L. Add a `bend_angle` parameter so the two flanges meet at an
arbitrary angle (e.g. 45°). **Sketch:** build the profile with the second flange rotated by the
angle; place that flange's holes along the rotated axis; keep it watertight/one-body. Add a
`bend_angle` (continuous/fixed) param read by `BracketParams.from_spec`, and teach the refiner the
phrasing ("bend at 45°", "make it an acute bracket").

### CALI-12 — Threaded / tapped holes (or insert bosses)  · P2 · generator · 🧊 backlog
"Thread the holes for M8 bolts." Options, cheapest first: (a) **tapped hole** = drill at the tap
diameter (M8 ≈ 6.75 mm) and label it threaded — no modeled helix; (b) **heat-set insert boss** =
counterbore sized for a brass insert (the FDM-friendly real-world answer); (c) **modeled helix
thread** via CadQuery sweep (heavy mesh, slow — last resort). Add a `hole_style`
(clearance|tapped|insert) parameter + the matching measurement/assertion. Note real threads ≠ a
bigger clearance hole.

## Epics / future (stories for later)
### CALI-13 — Primitive & geometry library + multi-part assemblies  · P2 · epic · 🧊 backlog
The corner bracket proved the loop; to make "all kinds of new parts" we need breadth of geometry.
A larger body of work, to scope and schedule later. Three threads:
1. **Lots of new primitives & geometries.** A library of parametric building blocks (plates, boxes,
   tubes, ribs, gussets, flanges, bosses, fillets/chamfers, lofts, revolves, patterns, sheet-metal
   bends, …) the generator/LLM can compose — the vocabulary for new part families beyond brackets.
2. **Multi-part assemblies that fit together.** Scheme out how Caliper represents *multiple* parts
   and the mating relationships between them (datums, joints, fits/clearances, fastener stacks),
   so the measurement layer can assert assembly-level constraints (no interference, mates, fit) —
   builds on the references/M3 work (CALI-10) but for our *own* generated parts, not just imported STLs.
3. **Run out the catalog.** Actually enumerate and implement the primitive/geometry list from (1)
   with tests + measurement coverage, turning the vocabulary into real, composable parts.
Known limitations that motivate this (logged 2026-06-11 from real use): no variable bend angle
(CALI-11), no threaded/insert holes (CALI-12), single part family only.

## Cross-cutting / infra
### CALI-0 — Project scaffolding  · P0 · M0 · ✅ done (`aa00b5d`, `45cd6b9`)
Repo init, conda env, package layout, PM board, nightshift loop/review/test scaffolding.
Env later rebuilt with micromamba (`e999d31`); zero-activation `make` targets (`2c64680`).
