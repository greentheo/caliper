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
- **Deferred:** webapp insert UI → CALI-21b; build assembly parts from a spec/intent → CALI-23;
  optimizer-in-the-author-loop for coupled inserts → CALI-24.

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
