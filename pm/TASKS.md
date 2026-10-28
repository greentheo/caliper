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
### CALI-10 — References  · P1 · M3 · ✅ done (`d402e38`)
STL intake as `role: fixed`; add `interference` + `min_clearance` measurements and assertions; iterate a part to fit a reference. The FEA-free Stage 2 loop.

**Shipped:**
- `measure.interference(g, ref)` → overlap volume (mm³) via a robust mesh boolean (manifold3d), AABB
  short-circuit + containment fallback; `measure.min_clearance(g, ref)` → signed gap (mm), negative =
  penetration depth. Both mesh-based so they work on raw STL references.
- Evaluator binds references to loaded geometry (`evaluate.load_references`, `references=` kwarg);
  an *unloaded* reference surfaces an actionable error rather than a silent pass.
- `decide` auto-routes fit failures (any `interference`/`min_clearance` assertion) to a size
  parameter, and `tune_continuous(prefer=…)` makes the fit **snug** — shrink just enough to clear,
  not collapse to the smallest part.
- `caliper fit SOURCE --ref ID=FILE.stl [--min-clearance MM] [--no-overlap] [--free PARAM]` — attaches
  the reference + fit assertions, promotes a size param to continuous, runs the loop. `make fit`.
- Demo fixture `examples/obstacle.stl` (+ `make_obstacle.py`). Tests: `tests/test_references.py`
  (11) + CLI fit smoke tests; full suite **90 passed**.

**Acceptance:** ✅ import STL as fixed · ✅ interference + min_clearance measured + asserted · ✅ a
part iterates to fit a reference (60mm bracket → 39mm to clear a block with 2mm clearance).

**Webapp fit UI (shipped):** `POST /api/fit` (base64 reference STL + pose + clearance) + a browser
flow — import an STL, drag/rotate it with a **TransformControls gizmo** (vendored, r160), Fit resizes
the part and re-renders. References carry a **pose** (`position` + `rotation` on `Reference`, three.js
XYZ euler) baked in at load (`measure.pose_matrix`/`from_stl_posed`), so what you place in 3D is
exactly what's measured. The viewer now renders the part in its **true build frame** (no recentring)
so part + reference share one coordinate system. Reference STL + pose persist in the run dir/meta and
re-render on reload. Verified in-browser (build → add ref → Fit → load fit run, ALL PASS).

**Follow-ups (not blocking):** `/api/fit` is synchronous and can be **slow for complex references**
(repeated mesh booleans × optimizer samples — a coincident full-bracket reference took ~30s; a simple
obstacle box is seconds) — consider fewer fit-grid samples or a background job + progress; multiple
references render one-at-a-time in the UI (loop supports N); penetration depth is sampled
(approximate) — fine for the pass/fail gate, exact depth would need a boolean.

---

## Generative generator — the spec's primary strategy (§2)
The MVP shipped with ONE hardcoded part family (the bracket); the LLM only drafts a spec / picks
params. The design spec's headline generation strategy is an **LLM-authored parametric script**, with
a **two-actor loop** (optimizer = continuous moves, LLM = structural edits). These two issues close
that gap — the difference between "a bracket parameter optimizer" and the measurement-grounded vibe-CAD
loop the spec describes. Picked over CALI-13 because it unlocks *arbitrary* parts and makes
breadth/multi-part cheap (the LLM composes geometry instead of us hand-coding each family).

### CALI-16 — LLM-authored generator  · P1 · generator · ✅ done (`c44403a`)
The LLM writes a CadQuery script from the spec; we run it **sandboxed**, measure it with the existing
loop, and feed **build errors (tracebacks) back** to the LLM to self-heal — the spec's "stack trace as
feedback," now closing on geometry.
- **Sandbox runner** (`sandbox.py` + `_sandbox_runner.py`): exec an authored script in a **subprocess**
  (timeout, temp cwd), export **STEP** (keeps the B-rep so hole/face probes still work), re-import in
  the parent → `Geometry`. Structured `{ok, error, traceback}`. Fully testable with no LLM.
- **Author** (`authoring.py`): spec → prompt → `build(params)` script; on build error, retry with the
  traceback (bounded). LLM call **injectable** (like `eval_fn`) so the mechanism tests without a key.
- **Wiring**: a generation-strategy switch — the hardcoded bracket stays as the offline / regression /
  fast path; LLM authoring is the general path (needs `ANTHROPIC_API_KEY`). The generated **script is
  stored per run** (`part.py`) — the spec says the script is the human-editable source of truth and
  must be diffable.
- **Security posture (local-trust):** subprocess + timeout, run on the user's own machine with their
  own key — threat model is "LLM writes runaway/buggy code," not a malicious attacker. A hard sandbox
  (container, seccomp, net block) is the Phase-2 hardening, noted but not built.
- **Acceptance:** an intent that ISN'T a bracket ("a phone stand", "a flanged tube") → LLM authors a
  script → it builds (self-healing a deliberate build error) → measures → report + STL, with `part.py`
  stored. Slice 1 proves author+build+measure; the iterate loop is CALI-17.

**Shipped:** `sandbox.py` + `_sandbox_runner.py` (subprocess, timeout, STEP export→re-import so B-rep
probes survive), `authoring.py` (injectable author + build-error self-heal), `caliper gen` + `make gen`,
`part.py` stored per run. **Verified live** (claude-sonnet-4-6): `caliper gen "a cylindrical desk cable
grommet, 40mm OD, 30mm bore, 25mm tall, 5mm flange"` → the LLM authored a real hollow tube + flange
union (with reasoning comments), built on attempt 1, watertight, correct OD/height/walls, **7/8 asserts
pass** (the 1 fail is the CALI-18 bore-probe nuance, not an authoring miss). Tests: `test_sandbox.py`
(5) + `test_authoring.py` (6, incl. self-heal) + CLI gen wiring + intake-normalize = **105 passed**.

**Bonus bugs fixed while here (LLM intake/refine were silently dead for the user's model):**
1. **Assistant-prefill rejected.** intake/refine ended the message list with an assistant turn (`{`);
   `claude-sonnet-4-6` 400s on that ("conversation must end with a user message") → intake *always*
   fell back to the offline bracket spec. Removed the prefill (extract_json already tolerates fences).
2. **Schema-laxness.** Even reaching the model, drafts didn't match the schema (bare-string assertions,
   params missing the `type` discriminator, `part_name`/`description` keys) → validation failed → silent
   fallback. Added a precise schema+vocabulary prompt and `normalize_spec_dict()` (tolerant coercion).
   Now `caliper gen "a grommet…"` yields a faithful `desk_cable_grommet` spec, not a bracket.

**Follow-ups:** CALI-17 (structural-edit loop — fix failing *assertions*, not just build errors);
CALI-18 (bore probe); webapp `gen` button; harder sandbox (container/net-cutoff) for untrusted use;
the author isn't yet given the measurement *report* to iterate dimensions (that's CALI-17).

### CALI-17 — Structural-edit loop  · P1 · loop · ✅ done (`6ee3e52`)
Make the LLM actually **revise the authored script** to fix a failing *measurement*, not just a build
error — completing the two-actor loop for LLM-authored parts.

**Shipped:** `authoring.improve(spec, author, max_rounds)` — each round the LLM writes/revises the
script, we build it sandboxed and measure it; a **build error → traceback feedback**, a **failing
assertion → the report (id + expr + actual + margin) feedback**, until green / oscillation / round
cap (mirrors CALI-6's rails). Author injectable → fully tested. Wired into CLI `caliper gen`
(`--max-rounds`) and the **webapp** (`POST /api/gen` + a "✦ author any part" toggle that routes Build →
`/api/gen`; authored `part.py` shown + persisted; reload shows it via `get_run`).
- **Verified live (CLI):** `gen "a hexagonal pen cup…"` ran 4 rounds (2 build-heals + 2 revisions) and
  honestly reported "best effort" — the 2 residual fails were a *contradictory intake-drafted assertion*
  (a hexagon can't be 60×60 in bbox) and *measurement noise* (min_wall 2.99 vs a hard ≥3.0), not author
  misses. **Verified in browser:** "✦ author any part" → "a round coaster with a 3mm raised lip" → ALL
  PASS in 1 round, rendered in 3D, authored script shown. No console errors.
- Tests: 4 `improve` tests (pass-first-try, heal-measurement, heal-build-then-measurement, oscillation)
  + `/api/gen` server test. **110 passed.**
- **Note:** this is a *separate* loop from the bracket `run_loop`/`decide` (which still dead-ends a
  structural failure at "stuck" — fine, the bracket family has no script to revise). The two converge
  once authored parts also get optimizer-tuned continuous params (a CALI-19 follow-on).

## Assembly spine — the path to multi-part design with fits & tolerances
The path to the north star ("insert a support between the wheel and the XYZ assembly"). Built on the
single-part loop (CALI-16/17) and CALI-10's two-body fit substrate. **Spine complete:** CALI-19 (fits) +
CALI-19b (multi-param optimizer) + CALI-20 (assembly model) + CALI-22 (author-loop fit/refine) all
shipped — **CALI-21 (insert-into-assembly) is now unblocked** and is the headline next step.

### CALI-19 — Tolerances & fits as first-class  · P1 · assembly-spine · ✅ done (`7d237cf`)
A vocabulary for *fits* + tolerant comparisons, so the loop can target a fit and noise stops causing
false failures. The user's "fits and tolerances" pillar.

**Shipped:**
- `tolerance.py`: printer-friendly **fit classes** (press/snug/slip/free/running) → `(lo, hi)` clearance
  bands (FDM-absolute, ~0.2 mm; gentle widening for big nominals). Helpers `approx(x, nom, tol)`,
  `within(x, lo, hi)`, `fits(clearance, kind)` bound into the evaluator namespace.
- Evaluator: **two-sided band margins** — `lo <= x <= hi` now reports a signed margin = distance to the
  nearest bound, so a fit band is *tunable* (was `None` before → optimizer couldn't steer).
- Optimizer: `tune_continuous` does **progressive refinement** (4 shrinking rounds) so it converges onto
  a narrow 0.2 mm band; `decide` skips the snug `prefer` for band targets so they centre in the band.
- `caliper fit --fit slip [--nominal MM]` and a **webapp fit-class dropdown** → a band assertion. Intake
  taught to write tolerant asserts (`approx`, bands) and **not** to assert internal features via `bbox.*`
  (the phone-stand `slot_fits_phone` bug).
- **Verified live:** `fit --fit slip` tuned a bracket 60 → 41.8 mm to land clearance = **0.188 mm**, dead
  centre of the slip band. Browser dropdown wired (hides manual clearance), no console errors.
- **Bonus guard (the fit bug they hit):** `fit`/`refine` **refused LLM-authored parts** (part.py present)
  with a clear message instead of silently rebuilding a bracket. _(Superseded by CALI-22 — they now route
  through the author loop and edit the real part.)_
- Tests: `test_tolerance.py` (8) + band-margin/fit-class loop + authored guards (CLI + server). **121 passed.**
- **Deferred:** multi-parameter (N-D) joint optimization → CALI-19b (now shipped).

### CALI-19b — Multi-parameter optimizer (coupled fits)  · P2 · assembly-spine · ✅ done (2026-06-12)
CALI-19's tuner is 1-D (one knob per failing check). Assembly fits *couple* — one clearance depends on
two dimensions, two mates fight over one wall — and tuning one knob at a time stalls at a saddle.
- **`decide.tune_multi(spec, params, eval_fn, engine="coord")`** searches the joint continuous space
  against a **global** objective: maximize `(all_pass, #passing, worst signed margin, −total normalized
  change)`. Worst-margin pushes every assertion over its threshold together; change-from-init keeps it snug.
- **Coordinate descent by default** (deterministic, eval-frugal — geometry rebuilds are the cost):
  sweep each knob over a coarse grid + a refined local window against the global score; stop when a
  sweep doesn't improve. **Escalates to seeded `scipy.optimize.differential_evolution` ONLY when CD
  can't reach feasibility** — the genuinely-coupled case. `engine="scipy"` forces the global search.
- **`decide` route 0:** with ≥2 continuous knobs and a failing numeric check, tune the whole vector;
  taken only if it improves (more passing / all-pass), else fall through to the 1-D + snug path.
  Single-knob specs are untouched.
- Tests: coupled 2-knob problem (`W+D` band + `W*D` budget, feasible only asymmetric) solved via CD→scipy
  escalation and via `engine="scipy"`; separable 2-knob solved by CD alone (spy asserts scipy unused);
  `decide` routes coupled failures to the multi move. **142 passed.**

### CALI-22 — Author-loop fit & refine  · P1 · generator · ✅ done (2026-06-12)
Fit/refine used to rebuild via the bracket generator, so they couldn't touch LLM-authored parts (guarded
in CALI-19 to fail honestly). Now they route through `improve()` **seeded with the run's `part.py`**, so
the LLM edits the real part — the front edge of CALI-21 (insert-into-assembly).
- **`improve(..., seed_script, seed_feedback, ref_base)`** — primes round 1 with an existing part + the
  new constraint (revise, don't restart). Same build-error + failing-measurement healing as `gen`.
- **`refit_authored(spec, script, …)`** — spec carries the reference + fit assertion (via
  `fit.attach_reference`); seeds the loop + feeds the fit checks. **`refine_authored(spec, script,
  instruction, …)`** — folds the instruction into `spec.intent` (so later rounds can't undo it) + seeds.
- **CLI** `fit`/`refine` of an authored run route through the loop (no more return-2). **Webapp**
  `/api/fit` + `/api/refine` route through (422 guards removed); shared `_finish_authored()` persists
  script+STL+refs; `/api/gen` refactored onto it.
- Tests: seed-priming, `refit_authored` (60→30 mm box clears a reference in 2 rounds, fed the failing
  `interference`), `refine_authored` intent-fold, CLI + server route-through. **138 passed.** Live LLM
  path needs `ANTHROPIC_API_KEY` (routing verified with injected authors).

### CALI-20 — Assembly model (N parts + interfaces)  · P1 · assembly-spine · ✅ done (2026-06-12)
Represent multiple parts, their **mates / datums / joints**, and **assembly-level assertions** (no pair
interferes, mates touch, fastener stacks align). Generalizes CALI-10's two-body interference/clearance
to N bodies with *named* relationships. "This collection of parts."
- **`assembly.py`** — `Part` (id + geometry `source` [STL or run dir] + placement position/rotation +
  role fixed|movable), `Mate` (`between: [a, b]` + kind `no_interference`/`clearance`/`fit`/`touch`),
  `Assembly` (parts + mates + assembly assertions). YAML/JSON round-trip; validates mate refs + dup ids.
- **Mates → measured assertions** (`mate_assertion`): touch → `-tol <= min_clearance(a,b) <= tol`; fit →
  CALI-19 band; clearance → `>= v`; no_interference → `interference(a,b) <= 0`. `derived_assertions`
  = per-mate then free-form assembly assertions.
- **N-body measure** — `pairwise_interference` (all pairs), `max_interference` ("nothing collides"),
  `min_pair_clearance` (tightest gap anywhere). Reuses the two-body probes (they already took any pair).
- **Evaluation reuses the single-part evaluator** — same AST interpreter, signed margins (fit band
  between two parts is tunable), same `Report`. Namespace: part ids → posed `Geometry`; probes take two
  parts; `max_interference()`/`min_clearance_all()`/`bbox(part)` bound in.
- **`caliper assemble <file>`** (+ `make assemble`); example `examples/assembly.yaml` (post-stand:
  base→post→cap, two touch mates) → ALL PASS. Tests: `test_assembly.py` (13). **134 passed.**
- **Deferred:** webapp assembly viewer → CALI-20b. Spec-source parts (build from a spec via the
  author/bracket generator at assemble time) → fold into CALI-21. Today parts load from STL / run dirs.

### CALI-21 — Insert-into-assembly  · P1 · assembly-spine · ✅ done (2026-06-12) — VERIFIED LIVE
Load an assembly, name two interfaces, ask for a part "here" at a target fit → the LLM authors a part
that **mates to both sides** with the right clearance, verified by measurement. The headline
interaction: "insert a support between the wheel and the XYZ assembly."
- **`insert.py`:** `insert_spec(asm, between, fit, new_intent, new_id)` → a spec whose **references are
  the existing parts, posed**, asserting a fit **band** vs each interface + `interference <= 0` vs every
  other part + one-body/watertight. `_bridge()` finds the separation axis + the two facing faces;
  `build_insert_intent()` hands the author the interface bboxes, gap, and facing-face coords in WORLD
  space so it builds *in place*. `insert_part()` runs the author loop (`improve`, injectable author);
  `add_part_to_assembly()` appends the part (run-dir source, identity placement) + two `fit` mates.
- **CLI** `caliper insert <asm> --between a,b --as id --intent "…" --fit slip --save out.yaml` + `make
  insert`: authors → persists STL + `part.py` → adds to the assembly → re-measures the whole assembly.
- **Verified live (real Claude API):** two posts, 50 mm gap → LLM authored a cross-bar **first try**,
  **0.21 mm clearance to each post** (centre of the slip band); the saved assembly re-`assemble`s green.
  The script reasons from the bboxes, applies the clearance, `.box(...)` in world coords. Also live-
  confirmed `gen` and authored `refine` ("6 mm taller in z" → edited the real `part.py`).
- Tests: `test_insert.py` (6). **148 passed.**
- **Deferred:** webapp insert UI → CALI-21b (done); build assembly parts from a spec/intent → CALI-23;
  optimizer-in-the-author-loop for coupled inserts → CALI-24.

### CALI-21b + CALI-20b — Webapp insert UI + assembly viewer  · P1 · M2 · ✅ done (2026-06-13) — VERIFIED LIVE
The CALI-21 headline, clickable in the browser: load an assembly, click two parts to pick interfaces,
choose fit + intent, Insert → the LLM authors the bridge, it renders green, the assembly re-measures.
- **Backend:** `GET /api/assemblies` (scan `CALIPER_ASSEMBLIES`, default `examples/`, for YAMLs that
  parse as Assembly), `GET /api/assembly/{id}` (parts + poses + stl_urls + measured report),
  `GET /api/assembly/{id}/part/{pid}.stl`, `POST /api/insert` (wraps `insert.insert_part` → persists
  the authored part as a run → `add_part_to_assembly` → saves `<id>.inserted.yaml` → re-measures →
  returns new-part stl_url + report + script + bridge).
- **Frontend:** Assemblies list; multi-part render (posed, role-colored, green=inserted); **click-to-pick**
  via raycast (drag/click disambiguated by pointer travel) + emissive highlight + picks readout; insert
  panel (intent/id/fit); `window.__asm` debug seam; filtered the benign `ResizeObserver loop` warning.
- **Fixed live:** double path resolution — `insert_spec` now stores **absolute** reference paths
  (`improve`/`load_references` was re-resolving a relative path against `ref_base`).
- **Verified live in-browser (Preview MCP + real API):** two posts → picked both → Insert → cross-bar
  authored in 1 round, rendered green, both mates 0.21 mm, nothing collides, saved as `insert_demo.inserted`.
- Tests: `test_server.py` +5 (list/get/part-stl/insert-route-through/400/404). **153 passed.**

### CALI-25 — A whole (small) machine: a corner leg  · P1 · assembly-spine · ✅ done (2026-06-13)
The real test of everything, passing. A 4-part **corner leg** — two solid **20×40 mm bars** (vertical
post + horizontal beam) at a right angle, a **gusset bracket**, and a **foot**, screwed with M5s through
**aligned holes** — `caliper assemble examples/machine.yaml` → ALL PASS (4 touch mates, no collisions,
3 hole-alignment checks at ~1e-15 mm). The predicted bottleneck (measurement vocabulary) was real and
addressed with a hole-alignment probe.
- **New measurement (`measure.py`):** `holes_world(g)` (holes transformed to the assembly frame via the
  part's `pose`) + `min_hole_misalignment(a, b)` (smallest perpendicular offset between a hole of `a`
  and a near-parallel hole of `b`; 0 = coaxial → a screw passes through both). Bound as
  `hole_misalignment(a, b)` / `holes_aligned(a, b, tol)`. Added `pose` to `Geometry`.
- **Parts** (`examples/machine/{bar_v,bar_h,corner_bracket,foot}.py` + `examples/machine.yaml`): built in
  world coords; tap-diameter holes in the solid bars (threaded), clearance holes in bracket/foot.
- Tests: `test_assembly.py` (+5). Verified CLI + in-browser (bracket bolt holes visible, ALL PASS).
- **Threaded** = tap-diameter holes (no modeled helix; the FDM-real answer). Full threads → CALI-12.

### CALI-23 — Assembly parts built from a script at assemble time  · P2 · assembly-spine · ✅ done (2026-06-13)
An assembly `Part.source` can be a CadQuery `build(params)` **`.py`** (not just STL/run-dir).
`assembly._build_py_local` runs it in the sandbox — keeping the **B-rep** so hole/face probes work —
cached by path+mtime; `_build_py_part` poses it. The machine's 4 parts use this. The webapp serves
`.py` parts as STL (local mesh; the front end poses it). *(Building from a free-text intent at assemble
time, vs a committed script, is a further step — left for later.)*

### CALI-26 — Per-part collision shading in the viewer  · P2 · M2 · ✅ done (2026-06-13)
`/api/assembly/{id}` and `/api/insert` return `collisions` (pairs with interference > 0); the viewer
shades any colliding part **red** (resets to its role color otherwise). *Mate lines deferred — the
report panel + red shading already make pass/fail and collisions obvious.*

### CALI-24 — Optimizer in the author loop  · P2 · assembly-spine · 🧊 backlog
Today an insert relies on the LLM revising dimensions to hit the fit. Fold CALI-19b's `tune_multi` into
the authored path so a part that mates **3+ faces at once** gets its continuous params *optimized*, not
just LLM-guessed. Likely: author a parametric `build(params)`, expose its params to `tune_multi`.

### CALI-27 — Assemblies / refine hardening  · P1 · M2 · ✅ done (2026-06-13)
Chase the rough edges hit in real use. Theo reported: confusing UI ("didn't know which options to
click"), adding parts "didn't seem to work", the machine "only made part of the machine", and "where is
it even hosted?"
- **The partial-machine bug (root cause):** `loadAssembly` fetched part STLs *sequentially with no
  `response.ok` check* — one failure threw out of the loop, stranding a partial machine on screen.
  Now: **parallel per-part loading**, render what succeeded, error bar **names what failed and why**,
  status shows `loaded N/M parts`; progress text explains first-load script builds (~5–20 s).
- **Server:** `assembly.load_parts_tolerant` (one broken part doesn't sink the assembly) +
  `part_errors` on `/api/assembly/{id}`; build errors surface the traceback's **last line** (the real
  exception). Stale error bar cleared per load.
- **UI:** "❓ How this works" primer (4-step flow + which actions need the API key); intent label =
  "describe **one part**" (a machine = an assembly — `gen` authors ONE watertight part by design);
  tooltips; Insert hint narrates each pick step and why the button is disabled.
- **Docs:** README "▶ Run it" → **`make serve` → http://127.0.0.1:8000 (local, not hosted)**;
  TESTING.md opens with the same; README status/layout refreshed.
- Tests +2 (tolerant load names the broken part; `/api/assembly` 200s with `part_errors`, good part
  serves, broken 422s). Verified in-browser with a deliberately-broken assembly. **158 passed.**

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

## Webapp follow-ups
### CALI-14 — SpaceMouse via 3Dconnexion NL-Proxy (driver coexistence)  · P2 · M2 · ⏸ phase 1 done (`9420ca8`), phase 2 blocked on telemetry
> **Next action (Theo):** in the webapp pick "Driver / NL-Proxy", accept the cert at
> `https://127.51.68.120:8181` once, click Connect, and paste back the on-screen `_3Dconnexion` API
> readout — that unblocks phase 2 (navlib camera wiring). WebHID mode works today (quit 3DxWare).
The WebHID path (CALI-9) needs the user to **quit 3DxWare** (raw HID can't be shared). This task adds
the *driver* path so the SpaceMouse works in the browser **and** Fusion/Prusa at once.
**Research (2026-06-12):** 3Dconnexion's web SDK connects to the **NL-Proxy** at
`https://127.51.68.120:8181/3dconnexion/nlproxy` over **WAMP/secure-WebSocket**, using a
driver-installed **certificate** (special loopback IP the cert is issued for). Apps load
3Dconnexion's own `3dconnexion.js` (the `_3Dconnexion` global) which handles the protocol and drives
the camera via the **Navigation Library (navlib)** callback interface (get/set camera matrix, view +
model extents, hit-testing, etc.). Official three.js sample exists but is Cloudflare-gated; lib is
proprietary/driver-served.
**Plan:**
- **Phase 1 (this session):** UI mode toggle (WebHID | Driver-NL-Proxy); dynamically load the proxy
  lib; attempt `new _3Dconnexion(...)` + connect; introspect the API surface and stream any telemetry
  to the on-screen readout; surface every failure (driver down, cert untrusted, lib missing) clearly.
  Cannot be verified here — needs Theo's hardware + 3DxWare.
- **Phase 2 (after on-hardware telemetry):** implement the navlib callbacks to drive the three.js
  camera; tune mapping; document the cert-accept step.
**Acceptance:** with 3DxWare running, the browser connects via NL-Proxy (no quitting) and the cap
navigates the model. Until then the toggle defaults to WebHID and Driver mode is labelled beta.

### CALI-15 — Recent parts (browse / load past runs)  · P1 · M2 · ✅ done (`b582b54`)
Every run already persists under `runs/<id>/`. Surface them so you pull up a part to view + edit
instead of always generating new.
**Acceptance:**
- Persist `report.json` + `meta.json` (part, status, label, timestamp) per run.
- `GET /api/runs` lists recent runs (newest first); `GET /api/runs/{id}` returns its spec + report +
  STL url without rebuilding (re-evaluates only for legacy runs missing `report.json`).
- Front end: a "Recent parts" panel; click a run → loads spec, report, and the mesh into the viewer;
  refine from there forks a new run. List refreshes after each run/refine.
- Tests: list + load endpoints (load OCCT-gated only for legacy backfill).

## Milestone M4 — the design session (conversational UI)
> The engine works; the UI is a control panel for the engine. M4 makes the product a **viewport + a
> conversation**: state what you're building, answer a few questions, click a part, talk about that part.
> Full rationale in [`specs/caliper-conversational-spec.md`](../specs/caliper-conversational-spec.md).
> Decisions taken up front (Theo, 2026-09-18): **chat-first on a single part** before decomposition;
> old panel **demoted to an Advanced drawer**, not deleted; assertion promotion is **proposed and
> confirmed**, never silent.

### CALI-28 — Design object + store  · P0 · M4 · ✅ done (`658c52e`)
The container that doesn't exist today: "the thing I am building" — root prompt, clarified requirements,
a part tree, and per-part feedback history. Everything else in M4 hangs off this.
**Acceptance:**
- `Design` model + `designs/<slug>/` on-disk layout per spec §3: `design.yaml`, `assembly.yaml`,
  `log.jsonl`, `parts/<id>/{part.py, spec.yaml, history.jsonl, versions/vNNN/}`.
- `assembly.yaml` is the **existing** `assembly.py` format — `evaluate_assembly`/`assemble`/`insert` work
  against a design unchanged; a **single-part design is a one-part assembly** (no second code path).
- Create / load / save round-trips losslessly. Slug collisions resolved deterministically.
- `add_part` / `update_part` write a new `versions/vNNN/` snapshot (part.py + report.json) and append a
  `history.jsonl` entry; nothing is ever overwritten in place.
- Requirements block (from the clarify round) is stored and retrievable as prompt context.
- `runs/` is untouched and still browsable; a design may adopt an existing run as a part.
- Tests: round-trip, versioning/snapshot, history append, one-part-design evaluates via `evaluate_assembly`.

### CALI-29 — Chat turn handler (scope-aware)  · P0 · M4 · ✅ done (`48a35fb`)
The loop behind the conversation: a message, optionally scoped to a clicked part, becomes an action.
**Acceptance:**
- `turn(design, message, scope=part_id|None)` → classify intent (clarify / author / refine / promote /
  answer) → dispatch to the **existing** engine (`authoring.improve`, `refine_authored`, `insert_part`).
- **Closes the biggest gap:** refine a part that lives *inside an assembly* — today `refine_authored` only
  works on a single-part run and assembly members are static `.py` with no revision path.
- After any geometry change, **re-measure the whole design** (every mate + assembly assertion) and report
  what the change broke, in the same turn.
- Unscoped message = design scope; scoped = that part. No mode toggles.
- Appends to `history.jsonl` (part) / `log.jsonl` (design) per spec §3.
- Tests: scope routing, refine-in-assembly rebuilds + re-measures, a cross-part break is reported.
- _Added during the task:_ a **`revert`** action — the break reply offered a rollback the handler had no
  verb for, and "roll it back" would have routed to *refine*. `DesignStore.restore` makes the undo a new
  revision, so it lands in the history rather than erasing it.

### CALI-30 — Feedback → assertion promotion  · P1 · M4 · ✅ done (`1855322`)
The idea that makes the history worth keeping: measurable feedback becomes a permanent test.
**Acceptance:**
- Given feedback + part context, draft an assertion in the **existing** expr vocabulary (§4 design spec).
- **Validate before offering:** it must parse and evaluate against the current geometry (no proposing a
  probe that doesn't exist or an expr that throws).
- **Proposed, never silent** — shown in chat, accepted/declined inline; accepted → appended to that part's
  `spec.assert` and enforced on every later build; declined → logged as a plain edit.
- Non-measurable feedback ("less chunky") is honestly labelled unenforceable, not faked into a number.
- Tests: promotion round-trip, invalid-expr rejection, decline path, regression caught on a later revision.
- _Added during the task, driven by the live run:_ promoted **design-level rules are shown to the
  author** (they were enforced but invisible, so a revision could violate a rule the human locked in);
  a proposal that doesn't hold now states that **the edit missed the ask**; and **conflict detection**
  names a rule the new one contradicts, retiring it on accept.

### CALI-31 — Streaming (job + SSE)  · P1 · M4 · ✅ done (`4fe957a`)
Authoring is many LLM round-trips over tens of seconds; the server is synchronous POST today, so the chat
would sit dead and read as broken.
**Acceptance:**
- `POST /api/design/{id}/chat` returns a job id immediately; `GET /api/design/{id}/events` (SSE) streams
  progress events (`authoring`, `built`, `measured`, `revising i/n`, `done`, `error`).
- Chat narrates each event; the viewport updates per part as parts complete (not one batch at the end).
- Errors surface the real exception line (the CALI-27 discipline), never boilerplate.
- Tests: job lifecycle, event ordering, error event carries the traceback tail.

### CALI-32 — Front end: viewport + chat  · P1 · M4 · ✅ done (`4fe957a`)
The reskin, once the machinery above is real.
**Acceptance:**
- Default page = 3D viewport + chat column. **Three surfaces only**: viewport, chat, Advanced drawer.
- Click a part → chat scopes to it (dismissible chip); unscoped = design scope.
- The internal-seam toggles are **gone from view**: "use Claude", "✦ author any part", offline-vs-LLM.
- Current panel survives **collapsed** behind Advanced: spec YAML, `part.py`, raw report.
- Keeps working: picking, collision shading, ⤢ fit, STL download, the error bar.
- Verified in-browser (Preview MCP, `caliper-web`), not just unit-tested.

### CALI-33 — Clarify round → stored requirements  · P1 · M4 · ✅ done (`4fe957a`)
Ask once, never re-ask.
**Acceptance:**
- A new design runs a **bounded** round of questions that actually change geometry (profile, drive, rail,
  process) — reuses `intake.py`'s ask-don't-assume gate; no interrogation, no unbounded loop.
- Answers stored as the requirements block in `design.yaml` and injected as permanent prompt context.
- Skippable: the user can say "just build it" and Caliper proceeds on stated assumptions.
- Tests: questions stored, requirements reach the author prompt, skip path works.

### CALI-38 — whittle bridge (aero / load studies)  · P1 · M4 · ✅ done (`4fe957a`)
Theo's sibling project **whittle** (`~/githubrepo/whittle`) evolves a part under physics and returns a
slider of stations. Caliper drives its local server over its JSON API — no whittle changes, no shared
Python env — so a design part can be studied and a station brought back.
**Acceptance (met):**
- Send a part (world coords, mm) with the setup Caliper knows pre-filled: flow, mirror, flat bottom,
  speed, budget, interior keep box; `flow` and `dual` (carve + lighten, held from underneath, cargo).
- **Carve where the air is:** `carve="tail"` lets whittle reshape only the downstream end, for a part
  riding behind something (the hitch box behind the car).
- Progress streams; every station is filed under `designs/<slug>/whittle/<run>/` with the run record.
- **Removal measured, not reported:** station volume vs the part as built (whittle's stations are voxel
  remeshes, ~½ voxel larger). Flow stations report force saved and **kWh / 100 mi**.
- **Bring a station back** as the part's current revision (a mesh; the script survives underneath, and
  "roll it back" returns to it). Caliper reports every side the shape grew past where the part was.
- Chat refuses to revise a whittled mesh's stale script (it would silently discard the carving).
- Tested against an in-process fake whittle (incl. one that inflates stations like the real one);
  verified live against Theo's running whittle.
**Not done, by design — needs whittle:** sheltering by the car. Uploading a frozen stand-in alongside
the part makes whittle carve nothing (one lattice spans everything). Needs obstacle bodies in whittle's
drag model. Coordinated with the whittle-agent session.

### CALI-39 — Parametric aero loop  · P1 · M5 · ✅ done (`abb1d59`) — on branch `cali-39-parametric-aero`; needs whittle at `a1248d1` (its `physics-and-slider`, committed 2026-10-27, not yet on whittle's main)
Return a **parametric** part, not a mesh. **Agreed split with the whittle-agent session (2026-10-27):**
whittle drives — its new `ParametricStudy(build, bounds, start=, flow=, speed_kmh=, obstacles=[car])`
searches the parameters against its drag model and returns the same volume-vs-drag slider, with
`sweep.at(x).design` → a params dict. Caliper supplies `build(params) -> (vertices, triangles)` straight
from CadQuery's `tessellate(0.5, 0.2)` (whittle welds + splits long edges), **in-process**
(`pip install -e ~/githubrepo/whittle` into the caliper env — dry-run clean: adds scikit-image only, no
numpy/scipy change). Scoring exact geometry removes the remesh inflation entirely. whittle is also adding
`obstacles=` (the car shelters, isn't scored or moved) — fixes the shelter problem for FlowStudy too.
**Caliper side:** a warm build worker (the sandbox's cold start is 1–2 s; ~5k builds per sweep), writing
the chosen design back as a new **parametric** revision of the part, and "Shape it for drag" in the UI.
Hitch-box params: `tail_len` 0–500 mm, `top_taper_deg` 0–20, `side_taper_deg` 0–15, `tail_edge_r` 5–100 mm,
optional `nose_top_r` 5–150 mm; flat bottom (sits on the frame).
**Shipped (2026-10-27):** `aero.py` (PARAMS read/rewrite by AST position, `study`, `adopt`),
`sandbox.BuildWorker` + `_build_worker.py` (warm sandboxed builds, ~0.13 s vs 1–2 s cold), the
PARAMS convention in every authoring prompt, `/api/designs/{slug}/aero*`, and "Shape it for drag" in
the inspector. Live: 4 tail params behind the car → **11 lbf ≈ 2.2 kWh/100 mi** at 7% of the volume,
returned as numbers in the script (envelope exact — no inflation). As built the params are mm-based
(`tail_len`, `tail_drop`, `tail_pinch`, `tail_edge_r`) rather than the angles first proposed.

### CALI-40 — Size a tube frame (whittle FrameStudy)  · P1 · M5 · ✅ done (`117960e`)
A part declares `members(params)` + `supports(params)`; whittle's FrameStudy (whittle-agent, branch
`frame-study`) analyses it under `standing` and `driving` cases and sweeps tube sizes per group; the chosen
tubes go back into PARAMS. Inspector: **Size the frame**. Next: plate mode for the gussets at the jog, fed by
the frame's end forces (`CaseResult.end_forces`); legs + the parked/sleeping case.

### CALI-41 — What a part is built from: weight, centre of gravity, bill of materials · P1 · M5 · ✅ done
A part's shape says nothing about its weight. A part now declares how it's built: a module-level `BUILD`
dict of choices (kept apart from PARAMS — they change weight, not shape) and `construction(params, build)`
returning pieces — **sheet** (flat `outline` or bent `facets`, thickness, `covers`), **stick** (lumber by
nominal size, steel tube by outer/wall), **lump** (mass at a point) — against `materials.py` (densities with
their basis, stock sizes, PMF/paint rates). `construction.py`: take-off → weight + CoG; BOM (sheets
shelf-packed on stock, cuts packed on sticks, canvas yd / glue / paint gal); what-ifs; `BUILD` written back
by AST position. `balance()` adds every weighed part (frames from `members()`, tubes with rounded corners at
nominal wall ≈ catalog lb/ft) and takes the moment about the first support (the receiver mouth), with an
optional payload on the floor. Inspector: **Built from** (pickers, *Use these*) and **Weight & balance**;
red dot = CoG, green = hitch. `shape_signature` ignores BUILD/construction/members/supports.
Next: CALI-42 re-size the frame from the box's real weight at its real CoG (1 in tube options);
CALI-43 cut plan + CNC DXF (panels flattened from their outlines — `flatten()` is the start).

## Milestone M5 — whole machines from one prompt (after M4)

### CALI-35 — Decomposition planner  · P0 · M5 · 🧊 backlog
Root prompt → part list with interfaces. The highest-value and least-proven capability; deliberately
scheduled *after* the interaction is proven, so the planner and a new UI aren't debugged simultaneously.
**Acceptance:** plan is emitted as an **assembly skeleton** (parts + mates + assertions) — i.e. something
measurable — reviewed before any geometry is authored; parts then authored in dependency order.

### CALI-36 — Nested sub-assemblies  · P1 · M5 · 🧊 backlog
Descend into a part that is itself a design (a "roller carriage" opens as its own part tree). Covers most
of the "zoom into components" ask without face-level picking.

### CALI-37 — Feature-level selection  · P2 · M5 · 🧊 backlog
Click a specific hole/face. Needs per-face group export + a B-rep face-id round-trip through the
tessellation. Deferred deliberately: the cheap 80% is "click the part, say *the 5mm hole on the top face*".

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
