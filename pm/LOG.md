# Caliper work log

Append-only. Newest first. One entry per shipped task or notable decision.
Format: `### YYYY-MM-DD · CALI-N · title` then what changed, tests, and the commit hash.

---

### 2026-06-12 · CALI-16 · LLM-authored generator (the spec's primary strategy)
- **Why:** the MVP shipped one hardcoded part family; the LLM only drafted a spec. The design spec's
  headline generation strategy (§2) is an **LLM-authored parametric script**. This builds it — the
  difference between "a bracket parameter optimizer" and the measurement-grounded vibe-CAD loop.
- **Sandbox** (`sandbox.py` + `_sandbox_runner.py`): authored scripts run in a **subprocess** (timeout,
  temp cwd), export **STEP** (keeps the B-rep so hole/face probes survive the process boundary), parent
  re-imports → `Geometry`. Any failure → structured `{error, traceback}` (the "stack trace" channel).
  Local-trust threat model; a hard sandbox (container/net-cutoff) is logged for untrusted use.
- **Author** (`authoring.py`): spec → `build(params)` script; on build error, retry with the traceback
  (bounded). The LLM call is **injectable** so author+heal is fully tested without a key.
- **CLI/wiring:** `caliper gen "<intent>"` / `make gen` — intake → author → build (self-heal) → measure
  → report → persist, storing `part.py` (the human-editable source of truth). Bracket path untouched.
- **Verified live** (claude-sonnet-4-6): `gen "a cylindrical desk cable grommet, 40mm OD, 30mm bore,
  25mm tall, 5mm flange"` → the LLM wrote a real hollow **tube + flange union** (with reasoning
  comments), built on attempt 1, watertight, correct OD/height/printable walls, **7/8 asserts pass**.
  The 1 fail is a measurement nuance (`largest_through_bore` counts the tube's outer wall as a bore →
  CALI-18), not an authoring miss.
- **Two LLM-intake bugs fixed along the way** (intake/refine had been silently dead for this model):
  (1) the **assistant-prefill** trick (`{`) made `claude-sonnet-4-6` 400 → always fell back to the
  offline bracket; removed it. (2) **schema-laxness** — model drafts didn't match the schema; added a
  precise schema+vocabulary prompt and `normalize_spec_dict()` (tolerant coercion). Now `gen` produces a
  faithful `desk_cable_grommet` spec, not a bracket.
- Tests: `test_sandbox.py` (5) + `test_authoring.py` (6) + CLI gen wiring + intake-normalize. **105
  passed.** Commit: c44403a

### 2026-06-12 · CALI-10 · Webapp fit UI + reference pose (in-3D placement)
- **Why:** fit was computed in baked coordinates — the reference had no pose, so it only "worked"
  because the demo obstacle STL was hand-authored in the bracket's frame. Real STLs (centered on their
  own origin) would land on top of the part. Fix: give references a **pose** and let you set it in 3D.
- **Reference pose:** `Reference` gains `position` (mm) + `rotation` (deg, three.js XYZ euler).
  `measure.pose_matrix` (scipy `XYZ` intrinsic, matches three.js) + `Geometry.from_stl_posed` bake the
  pose at load, so the fit probes stay pose-agnostic and the measured pose == what you see.
- **Backend:** `POST /api/fit` (base64 reference STL + pose + clearance/no-overlap + optional `free`
  param) → attaches a posed reference, promotes a size param, runs the loop, persists. Reference STL is
  copied into the run dir + recorded in `meta.references` (pose + serve url); served at
  `/api/runs/{id}/ref/{ref_id}.stl`; `get_run` returns references so a reloaded fit re-renders. Shared
  fit logic factored into `caliper/fit.py` (used by CLI + server; CLI `_cmd_fit` refactored onto it).
- **Front end (no-build):** vendored `TransformControls` (r160). Import an STL → renders
  **semi-transparent** with a move/rotate **gizmo** (W/E keys, mode buttons) → **Fit** reads the pose,
  POSTs, swaps in the resized part. The viewer now renders the part in its **true build frame** (no
  `geom.center()`) and frames on the combined part+reference bbox, so both share one coordinate system.
  Loading a past fit run re-renders its reference at the stored pose.
- **Verified in a real browser (Preview MCP):** build → import a box STL (gizmo appears) → Fit → server
  resizes + re-renders; loaded run_0026 shows the blue bracket pulled back from the orange reference at
  `[52,0,2]` with ALL PASS and `min_clearance(obstacle) actual=3`. No console errors.
- **Known caveat:** `/api/fit` is synchronous; a *coincident full-bracket* reference took ~30s (many
  mesh booleans × optimizer samples). A simple obstacle box is seconds. Logged as a follow-up.
- Tests: `tests/test_server.py` fit end-to-end + 404 (now **92 passed**). Commit: 6f048a8

### 2026-06-12 · CALI-10 · References / fit-to-reference (M3)
- **Measurements (real now, no longer deferred):** `measure.interference(g, ref)` → overlap volume in
  mm³ via a robust mesh boolean (manifold3d), with an AABB short-circuit and a containment-sampling
  fallback if the boolean kernel is missing; `measure.min_clearance(g, ref)` → signed gap in mm
  (positive = thinnest air gap from surface-proximity sampling, negative = deepest penetration). Both
  operate on meshes so they work directly on imported STL references. A `_as_mesh` coercer accepts a
  `Geometry`, a raw mesh, or a wrapper.
- **Reference binding:** `evaluate.load_references(spec, base_dir)` loads each `role: fixed` STL into a
  `Geometry`; `build_context`/`evaluate` take a `references=` map and bind `interference`/`min_clearance`
  to the real geometry. An *unloaded* reference resolves to an opaque handle so a fit check errors
  loudly instead of silently passing. `loop.make_eval_fn(references=…)` loads once and caches.
- **Snug fit:** `decide` auto-routes any failing `interference`/`min_clearance` assertion to a size
  parameter (`FIT_PARAM_PREFERENCE`), no per-spec id wiring. `tune_continuous(prefer=…)` adds a
  minimal-change objective: among feasible candidates pick the one closest to the original size, so the
  part shrinks *just enough* to clear (not down to the floor).
- **CLI/UX:** `caliper fit SOURCE --ref ID=FILE.stl [--min-clearance MM] [--no-overlap] [--free PARAM]`
  attaches the reference + fit assertion(s), promotes a fixed size param to a continuous range, runs the
  loop, persists a new run. Defaults to no-collision if no constraint given. `make fit`. Demo fixture
  `examples/obstacle.stl` (+ `make_obstacle.py`); `.gitignore` keeps `examples/**/*.stl`.
- **Verified end-to-end:** 60mm bracket vs a block at x∈[42,62] → fit shrinks the leg to 39mm for a
  clean ≥2mm clearance (`min-clearance 2`), or to 42mm just-touching for no-overlap. Tests:
  `tests/test_references.py` (11) + 2 CLI fit tests; updated the two evaluator/measure tests that
  assumed deferral. Full suite **90 passed**.
- Commit: d402e38

### 2026-06-12 · CALI-15 · Recent parts (+ hole-count hang fix)
- Browse/load past runs instead of always generating new. Persist `report.json` + `meta.json`
  (part, status, label, timestamp) per run; `GET /api/runs` (list) + `GET /api/runs/{id}` (load spec +
  report + STL without rebuilding; re-evaluates only for legacy runs). Front end: "Recent parts" panel,
  click to load the spec/report/mesh, active highlight, refresh after each run/refine; refine forks a new run.
- **Bug found while testing (real hang):** intent "…for **2020** with **two** M6 holes" mis-parsed the
  extrusion size 2020 as the hole count → generator tried to drill 2020 holes → CadQuery hung (POST
  never returned). Fixed: `_parse_holes` anchors the count on "holes" and limits it to a 1–2 digit /
  word number (so 2020 can't be the count) + clamp 1–12; defensively clamp `holes_per_leg ≤ 8` in the
  generator so no bad count can ever hang the kernel.
- Verified in-browser: build (1 iter, fast), new part tops the list with its label/timestamp, clicking
  an older run loads it (incl. legacy re-evaluate). Tests: **76 passed** (+5: list/load, parse, clamp).
- Commit: b582b54

### 2026-06-12 · CALI-9 · SpaceMouse: grid rotates with the part
- Feedback (real-use): with the SpaceMouse, the part rotated/panned/zoomed but the ground grid didn't
  rotate (it panned/zoomed fine). Cause: rotation spun the model *group* while the grid was parented to
  the world; pan/zoom move the camera so the grid followed those but not rotation.
- Fix: parent the GridHelper to `modelGroup` so rotation carries the plane with the part — pan/zoom
  (camera) and rotation (group) are now visually consistent. Verified render (no regression); rotation
  feel pending Theo's confirmation on hardware. 71 passed.
- Commit: cae162f

### 2026-06-12 · CALI-14 · SpaceMouse NL-Proxy (driver coexistence) — phase 1
- WebHID needs the user to quit 3DxWare (raw HID can't be shared — confirmed on Theo's SpaceMouse
  Compact `256f:c635`: "Failed to open the device" while the driver holds it). CALI-14 adds a *driver*
  path that coexists with Fusion.
- Researched the integration: NL-Proxy at `https://127.51.68.120:8181/3dconnexion/nlproxy`, WAMP/WSS,
  a driver-installed cert, and 3Dconnexion's `_3Dconnexion` lib driving the camera via navlib callbacks.
- Phase 1 shipped: UI mode toggle (WebHID | Driver/NL-Proxy beta); driver mode loads the proxy lib,
  instantiates `_3Dconnexion`, attempts connect, and reports the API surface + errors on-screen (cert
  hint included). Verified the graceful-failure path in the preview (no driver → clear error, no crash).
  Cannot verify the happy path here — needs Theo's hardware + 3DxWare; phase 2 (camera nav) follows the
  on-screen telemetry. 71 passed.
- Commit: 9420ca8

### 2026-06-12 · CALI-9 · webapp fix — vendor three.js locally (no CDN)
- Bug (real-use): on Theo's machine the Build button did nothing + a 404 in devtools. Cause: three.js
  was imported from the **unpkg CDN**; when that's blocked/offline/flaky the module import fails and
  `app.js` never finishes loading, so no event handlers attach. (Worked in the test browser where the
  CDN resolved — hence missed.)
- Fix: **vendor three.js locally** (`web/static/vendor/three/` — three.module.js + OrbitControls +
  STLLoader) and point the import map at local paths. App is now self-contained and works offline.
- Also: `<link rel="icon" href="data:,">` to kill the noisy favicon 404; an on-page error bar that
  shows load/runtime errors (so a dead button is never silent again); recursive package-data glob.
- Verified in-browser: zero external requests (all `localhost`), build → ALL PASS + render. 71 passed.
- Commit: 95a2e4a

### 2026-06-11 · 🎉 M2 COMPLETE · CALI-9 · webapp + SpaceMouse
- **FastAPI backend** (`server.py`): `/api/run`, `/api/refine`, `/api/runs/{id}/part.stl`,
  `/api/health` — reuse the library; persist runs; serve a no-build front end. `caliper serve` +
  `make serve`.
- **Front end** (`web/static`, no build step — three.js ESM via import map): intent box, refine box,
  measurement report panel (✓/✗ + margins + changes + clarify question), spec view, STL download, and
  a three.js viewer (STL loader + orbit, grid, lighting).
- **3Dconnexion SpaceMouse** (Theo's key ask) via **WebHID**: "Connect SpaceMouse" button →
  `navigator.hid`, 6DOF int16 axes → model rotate + camera pan/dolly, deadzone/gains tweakable, live
  axis readout, graceful fallback to mouse. Works in Chrome/Edge over localhost.
- **Verified in a real browser** (preview MCP): page loads error-free, `Build it` → ALL PASS report +
  bracket rendered in 3D; `Refine "make the holes 8mm and add a rib"` → "hole Ø 5.2 → 8.0, rib 0→1",
  re-measured, viewer reloaded the new mesh; STL downloads. Screenshotted both.
- Fixes found via the browser/test loop: FastAPI body models must be module-level under
  `from __future__ import annotations` (else 422); refine parser now handles "8mm" (no space) and
  prefers an explicit mm value over an M-size; a TDZ bug (`smOn` read before init in the render loop);
  dev `Cache-Control: no-store` so the browser never serves a stale module.
- Tests: **71 passed** (added server tests via FastAPI TestClient + refine regressions).
- Commit: 3c78fff

### 2026-06-11 · CALI-1.M1 · refine parser — per-side & word-number hole counts
- Real-use gap: "only do one hole on each side … in the middle" wasn't recognized (parser only knew
  digit + plural "N holes" as a *total*).
- Now the count parser accepts singular "hole", word-numbers ("one".."ten"), and **per-flange**
  phrasing ("on each side", "per leg") → doubles to the total. A single hole per flange is centred
  by the generator's positioning; "middle"/"centre" is acknowledged in the change list.
- Tests: **63 passed** (added 2). Verified the user's exact instruction → hole count 4 → 2,
  `bolt_pattern count=2`, ALL PASS, new STL.
- Commit: c9523c8

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

### 2026-06-11 · CALI-0 · canonical OCCT env via micromamba (Plan B) + zero-activation workflow
- Anaconda's classic solver stalled 55+ min on cadquery. Switched to standalone **micromamba**
  (osx-arm64), which solved + built the env in <1 min at `/opt/anaconda3/envs/caliper`:
  **cadquery 2.7.0 / occt 7.8.1 / ocp 7.8.1.2 / python 3.11**. Then `pip install -r requirements-pip.txt`.
- cadquery 2.7 dropped the `nptyping` dep → no numpy shim needed (unlike the pip-2.4 scratch venv).
- **`make test` → 47 passed** in the canonical env (auto-resolves the prefix), confirming the code
  works on cadquery 2.7 (not just the 2.4 used for the earlier scratch verification). CLI run → STL ✓.
- Editable-installed the package (`caliper` command) and added `make install`/`make run` targets that
  resolve the env python directly — no shell activation needed. Updated README/environment.yml to
  recommend the micromamba recipe.
- Commits: `e999d31` (micromamba env), `2c64680` (make targets + zero-activation docs).

### 2026-06-11 · 🎉 M0 COMPLETE · CALI-2/4/8 verified end-to-end with real geometry
- Verified the OCCT-dependent path. Fixed a generator bug: the CadQuery `"XZ"` plane normal is
  `(0,-1,0)`, so `extrude` is sign-defined and left the body off-centre on Y (bolt holes landed at
  the flange edge). Now recentre from the actual bounding box.
- **CALI-4** generator confirmed: corner bracket builds watertight, one body, 4×Ø5.2 holes on the
  bolt circle, optional Ø10 cable bore.
- **CALI-2** B-rep hole detection + `holes_matching(on=circle(60), count=4)` confirmed.
- **CALI-8** `caliper run "...four M5 holes and a cable pass-through" --no-llm --yes` → draft spec →
  clarify gate → loop → **ALL PASS** (bbox [60,20,60], min_wall 2.99, 4×Ø5.2 ✓, mass 8.1 g,
  watertight 1 body, bore Ø10) → 128 KB `runs/run_0000/part.stl`.
- **Full suite: 47 passed.** Verified in a pip CadQuery scratch venv (numpy-2 alias shim for the
  abandoned `nptyping`) because the conda env was still solving; re-confirmed later in the conda env.
- Commit: `ff8e154`.

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

### 2026-06-11 · CALI-0 · project scaffolding + environment
- Initialized local git repo. Created `src/caliper/` package layout, `tests/`, `pm/`, `nightshift/`.
- Stood up the .md PM system: `BOARD.md`, `TASKS.md`, `LOG.md`, `pm/README.md`.
- Adopted ai-night-shift conventions locally (loop/review/test guard) without cron — see `nightshift/`.
- Env: moved all non-OCCT deps to a pip layer (`requirements-pip.txt`) so conda only resolves
  `cadquery` under strict conda-forge priority (the full mixed-channel solve stalled).
- Decisions: conda for the env; nightshift conventions-only (no autonomous cron yet); start M0 core.
- Commits: `aa00b5d` (scaffolding + M0 skeleton), `45cd6b9` (lean conda env).
