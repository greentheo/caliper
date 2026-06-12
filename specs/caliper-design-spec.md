# Caliper — design spec

*Working codename. Caliper, because the whole thesis is that **measurement is the source of truth**, not vibes. Rename freely.*

A spec-driven system that turns loosely-stated intent into manufacturable 3D geometry by closing a measurement-grounded feedback loop: natural language in → executable spec → generated mesh → measured against the spec → iterate until it passes.

---

## 1. The idea

Generating CAD from an LLM fails today for one reason: no graded signal. You emit an OpenSCAD program blind, it renders (or doesn't), and nobody — human or model — knows whether it actually meets the requirement until eyeballing it. Code doesn't work that way: you run it, get a stack trace, get failing tests, get output. The fix is to give geometry the same loop.

The non-obvious part: the richest feedback channel is **not** "seeing." A vision model looking at a render is metrology by vibes — good for gross/topological errors (hole on the wrong face, bodies that don't touch, upside-down), useless for a dimension. The channel that actually closes the gap is everything you can **compute exactly** off the geometry: bounding box, wall thickness, hole inventory, interference against reference parts, mass, watertightness. Numbers are ground truth; the render is a sanity check. **Never let the vision channel report a measurement.**

This makes the whole thing **test-driven development for physical parts**:

| Software TDD | Caliper |
|---|---|
| Test suite | The spec's `assert` block |
| Compiler / runtime | Geometry kernel (CadQuery/OCCT) |
| Stack trace | Kernel build errors |
| Test output | Measurement report (value + margin per assertion) |
| Source of truth | The parametric script (human-readable, editable) |
| Refactor | LLM structural edits + optimizer dimensional tuning |

---

## 2. Core objects

- **Intent** — the human's loose natural-language ask. ("A corner bracket joining two 2020 extrusions, with a cable pass-through.")
- **Spec** — the executable contract derived from intent. Four parts: parameters, references, assertions, machine profile. The human can read and edit it; it's the negotiating surface.
- **Generator** — turns a spec into geometry. Primary strategy: an LLM-authored parametric script (CadQuery/build123d). Secondary strategy (later): free-form structural fill (the Stage 2 topopt engine).
- **Sensing layer** — measures generated geometry. Numeric probes (exact) + render probes (for vision).
- **Evaluator** — runs each assertion against the measurements, producing a pass/fail report with the actual value and the margin.
- **Loop / orchestrator** — the agent that reads the report and decides the next move until the spec is green or it gives up.

Two actors make moves, split by the **type** of decision — this split is the antidote to the LLM hallucinating dimensions:
- **LLM** makes *discrete / topological* moves: add a rib, move a hole to the other face, split into two bodies, restructure.
- **Numeric optimizer** makes *continuous* moves: given fixed structure, find the parameter values that satisfy the numeric assertions (mass, fit, clearance). The LLM never guesses a number — it sets up a search and hands it to a solver.

---

## 3. The spec format

A spec is data (YAML/JSON or a typed Python object). Worked example:

```yaml
part: corner_bracket

intent: >
  A bracket that bolts two 2020 aluminium extrusions at 90 degrees,
  with a hole through the middle big enough to route a cable bundle.

references:                      # imported fixed geometry (STL)
  - id: ext_a
    file: extrusion_a.stl
    role: fixed                  # never moves; mate to it, don't intersect it
  - id: ext_b
    file: extrusion_b.stl
    role: fixed

machine: ender3                  # profile = constraint bundle (mostly deferred, see §7)

parameters:
  wall:        {type: continuous, min: 2.4, max: 6, init: 3, unit: mm}  # optimizer tunes
  rib_count:   {type: discrete, choices: [0, 1, 2], init: 1}            # search/LLM picks
  cable_bore:  {type: continuous, min: 6, max: 14, init: 10, unit: mm}
  bolt_circle: {type: fixed, value: 60, unit: mm}

assert:
  - id: fits_bed        # maps to bounding_box()
    expr: bbox.dx <= 220 and bbox.dy <= 220 and bbox.dz <= 250
  - id: walls_printable
    expr: min_wall >= 2 * machine.nozzle          # 0.8 mm
  - id: bolt_pattern
    expr: holes_matching(Ø=5.2, on=circle(60), count=4)
  - id: no_collision
    expr: interference(ext_a) == 0 and interference(ext_b) == 0
  - id: mates_a
    expr: min_clearance(ext_a) <= 0.2             # actually touches the rail
  - id: cable_fits
    expr: largest_through_bore >= 8
  - id: mass_budget
    expr: mass(density=1.24) <= 80                # PLA, grams
  - id: one_body
    expr: body_count == 1 and is_watertight
```

Notes that matter for implementation:

- **Parameter kinds drive who controls them.** `continuous` ranges go to the optimizer. `discrete` choices go to LLM/search. `fixed` values are locked. This typing is what cleanly divides labor.
- **Assertions are predicates over measurement outputs.** Each `expr` references one or more sensing functions (§4). The evaluator parses these and reports `actual` + `margin`, not just a boolean.
- **Intent is the un-formalized residue.** The intake step (§5) converts as much intent as it can into assertions, then *asks the human* about the rest rather than inventing acceptance criteria. "You said 'sturdy' — what load, in what direction?" Ask-don't-assume is a hard rule.

---

## 4. The sensing / measurement API

The contract the agent and evaluator call. Prefer querying the **B-rep model** (CadQuery/OCCT) where possible — features like holes, faces, and walls are cheap and exact on a B-rep and hard on a raw triangle mesh. Mesh-only measurements are the fallback for free-form geometry that has no B-rep.

```python
# --- Dimensional (mesh or B-rep) ---
bounding_box(g) -> {dx, dy, dz, min:[x,y,z], max:[x,y,z]}
volume(g) -> float                     # mm^3
mass(g, density) -> float              # grams
center_of_mass(g) -> [x, y, z]

# --- Features (best on B-rep) ---
min_wall_thickness(g) -> float         # ray-cast / SDF-sample / medial axis
holes(g) -> [{center, axis, diameter, depth}]
holes_matching(diameter, on, count, tol) -> bool
largest_through_bore(g) -> float
faces(g) -> [{type: plane|cylinder|..., normal, area}]

# --- Relational, vs a reference ---
interference(g, ref) -> {overlap_volume, max_penetration}   # boolean intersection
min_clearance(g, ref) -> float
mates(g, ref, tol) -> bool

# --- Topological ---
is_watertight(g) -> bool
is_manifold(g) -> bool
body_count(g) -> int

# --- Visual (the vision channel — sanity only, never measurement) ---
render_views(g, views=["front","top","iso"]) -> [image]
section(g, plane) -> image

# --- DEFERRED (Phase 2+) ---
# overhang_area(g, angle, build_dir) -> float
# slice(g, profile) -> {print_time, support_volume, sliceable}
# fea(g, loads, supports, material) -> {max_stress, deflection, safety_factor}
```

Implementation backing: `trimesh` for mesh-side measurements and STL I/O, the CadQuery/OCCT model for B-rep feature queries, `manifold3d` for robust booleans (interference, clearance), `pyrender`/`trimesh` for the render probes.

---

## 5. The loop / workflow

```
intent ──► [intake] ──► spec ──► [generate] ──► geometry ──► [build?] ──┐
              │                                                          │
              │ (clarify gate: ask, don't invent)         build error ──┘
              ▼                                                  │
         human confirms spec                                     ▼
                                                            [sense] ── numeric probes + renders
                                                                 │
                                                                 ▼
                                                            [evaluate] ── report: per-assertion value + margin
                                                                 │
                                            ┌────── all pass ────┴────── failures ──────┐
                                            ▼                                            ▼
                                        done → STL                              [decide next move]
                                                                                   │        │
                                                              continuous fail ─────┘        └──── structural fail
                                                                   ▼                                    ▼
                                                            optimizer tunes params              LLM edits the script
                                                                   └──────────────► back to [generate] ◄┘
```

Step detail:

1. **Intake.** LLM reads intent + references + machine, drafts the spec. Formalizes every requirement it can into a typed parameter or an assertion. Surfaces ambiguities as questions and **stops** for human confirmation before building. Output: a spec the human has signed off on.
2. **Generate.** Produce/edit the parametric script (primary) or invoke a free-form strategy (later). First pass is a rough scaffold.
3. **Build.** Run the kernel. Build errors are first-class feedback (the "stack trace") routed straight back to the LLM.
4. **Sense.** Run the probes the active assertions actually need (don't measure what nothing asserts). Render canonical + section views.
5. **Evaluate.** Each assertion → `{pass, actual, margin}`. This structured report — *not* a blind render — is the agent's input.
6. **Decide.** All green → emit STL + report margins (optionally propose tightening). Failures → route by type: continuous-numeric failures go to the optimizer (tune `wall`, `cable_bore`…); structural/topological failures go to the LLM (add a rib, move a hole). Loop.

**Tier the feedback by cost** so the loop stays fast: cheap checks every iteration (build, bbox, interference, wall — ms); expensive checks only once cheap ones pass (renders; later, slice/FEA — s to min). No point rendering a part that doesn't fit the bed. Cap iterations and detect oscillation; the optimizer handles continuous search precisely so the LLM isn't flailing on numbers.

---

## 6. Architecture

```
┌────────────────────────── Webapp (React + three.js) ───────────────────────────┐
│  intent box │ spec editor (live) │ 3D viewer │ measurement report │ STL download  │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                     │ HTTP / WS
┌────────────────────────── Orchestrator (Python, FastAPI) ────────────────────────┐
│  Intake (Claude API)   Decide (Claude API)   Optimizer (nevergrad / scipy)        │
│        └──────────────── Loop controller ────────────────┘                        │
├───────────────────────────────────┬──────────────────────────────────────────────┤
│  Generator                         │  Sensing layer                                │
│   • parametric: CadQuery/build123d │   • measurement API (§4)                      │
│   • free-form: Stage 2 topopt (P2) │   • trimesh, manifold3d, OCCT queries, render │
├───────────────────────────────────┴──────────────────────────────────────────────┤
│  Geometry kernel: OpenCASCADE (B-rep) + mesh (trimesh)   │  Store: specs, runs, STL │
└──────────────────────────────────────────────────────────────────────────────────┘
```

- **Generator** keeps the B-rep alive as long as possible (richer measurement) and meshes only at the boundary (rendering, STL export, mesh-only probes).
- **Orchestrator** is the agent loop. Two Claude calls play different roles: *intake* (intent→spec, clarify) and *decide* (read report → next structural move). The *optimizer* is a separate, deterministic component the orchestrator delegates continuous search to.
- **Store** keeps every run (spec + script + measurements + STL) so iterations are diffable and reproducible — this is what makes it feel like git for parts, and what makes a good demo.

Stack: React + three.js (viewer), FastAPI (backend), CadQuery/build123d + OCCT (generate + B-rep), trimesh + manifold3d (measure + STL), Claude API (intake/decide), nevergrad or scipy.optimize (continuous tuning).

---

## 7. How Stage 2 folds in (and the scoping call)

The earlier Stage 2 PoC was: import STLs → build voxel masks → **topopt** a connector. Two parts of it survive into Caliper, but on different timelines:

- **Survives into the MVP:** the **reference-STL intake** (load fixed parts, treat them as `role: fixed`) and the **iterate-against-constraints loop skeleton**. These are exactly §5. You can iterate *parametric* geometry against *geometric* assertions (fit, clearance, mass, no-collision) with the optimizer — **no FEA required**.
- **Deferred to Phase 2:** the **topopt engine itself**. Its objective *is* an FEA solve, and you've (rightly) scoped sim out for now. So topopt arrives as a second generation strategy when FEA lands — "connect A to B carrying load L, minimize material" — feeding the *same* measurement/evaluate layer as the parametric path.

So: **fold in Stage 2's loop and reference handling now; bring in Stage 2's topopt engine with FEA later.** The measurement API (§4) is the shared spine both generation strategies plug into, which is what keeps the architecture honest as you add backends.

Deferred for now, per your scoping: FEA, slicer-in-loop, full printability (overhang/segmentation), machine profiles beyond a stub. The `machine` field and the deferred probes stay in the schema as no-ops so nothing has to be re-plumbed later.

---

## 8. MVP — the shortest path to something real

**Goal of the MVP:** demonstrate the magic loop — *loose idea → tech spec → real mesh → measured against spec → one iteration → downloadable STL* — and nothing else. No FEA, no slicer, no printability beyond a wall-thickness number, no topopt.

**Thinnest vertical slice:**
> Type "a 60 mm corner bracket for 2020 extrusion with four M5 holes" → system drafts a spec and asks one clarifying question → you confirm → it writes a CadQuery script, builds it, measures it, shows the report (bbox ✓, 4×Ø5.2 holes ✓, mass = 47 g ✓, min_wall = 2.1 mm ✓) and a 3D preview → you say "make the holes 8 mm bigger spacing" → it re-derives, regenerates, re-measures → you download the STL.

**Build it as a library first, UI second** — the loop is the product; the webapp is a wrapper. Milestones:

- **M0 — one-shot core (CLI, no UI).** `intent → spec(JSON) → cadquery script → mesh → measure → report`. Hardcode one part family (brackets). Proves intent→spec→geometry→measurement end to end.
- **M1 — one iteration cycle.** Feed the report back to the decide step; support a single NL refinement and a single optimizer tune on one continuous parameter. Proves the *loop*.
- **M2 — webapp wrapper.** FastAPI around the library; React + three.js front end: intent box, live spec editor, 3D viewer, report panel, STL download. Proves it's *usable* and demoable (the YouTube moment).
- **M3 — references.** Import an STL as `role: fixed`; add `interference` and `min_clearance` assertions; iterate a part to fit it. This is the Stage 2 loop, FEA-free.

**MVP measurement subset** (everything else stays stubbed): `bounding_box`, `volume`, `mass`, `min_wall_thickness`, `holes` / `holes_matching`, `is_watertight`, `body_count`, `render_views`, and (M3) `interference` / `min_clearance`.

**MVP stack:** CadQuery + trimesh + manifold3d + Claude API + FastAPI + React/three.js. That's it.

---

## 9. Roadmap (epics)

- **Phase 0 — MVP.** M0–M3 above. NL→spec, parametric generation, core measurement, the loop, references.
- **Phase 1 — robustness.** Better intake (clarify gate, ambiguity detection); more part families; B-rep feature detection hardening; run history / diffing; optimizer over multiple parameters.
- **Phase 2 — manufacturing.** Machine profiles as real constraint bundles; overhang/printability probes; slicer-in-loop (PrusaSlicer/Cura CLI); big-print auto-segmentation with joints; the Stage 2 topopt generation strategy (brings FEA).
- **Phase 3 — simulation & retargeting.** FEA-in-loop (load assertions, safety factor); optimizer driving structural objectives; multi-machine retargeting (same spec → printer vs CNC plasma flat-pattern); nesting for sheet processes.

---

## 10. Risks / open questions to track

- **NL → assertion drift.** The intake step inventing acceptance criteria silently is the top failure mode. Mitigation: hard ask-don't-assume gate, human-confirmed spec before any build.
- **Parametric-edit reasoning.** "Edit the script to fix a failing assertion" is the LLM's weakest step — but the one the loop most improves, since precise failure reports (value + margin + section view) are far easier to act on than a blank render. Track edit success rate as a metric.
- **Vision ≠ metrology.** Enforced architecturally: the render channel is forbidden from producing numbers. Worth a lint.
- **B-rep vs mesh.** Feature measurements degrade on raw meshes. Decision: keep B-rep authoritative; only the free-form/topopt path falls back to mesh-only probes (and it only needs the mesh-friendly subset).
- **Local minima / oscillation.** Iteration cap + oscillation detection; lean on the optimizer for continuous search so the LLM isn't guessing dimensions.
- **Determinism / reproducibility.** Same spec should give the same part. Seed and store everything; this also makes the demo and debugging sane.

---

## 11. Suggested starting backlog (seed for Linear)

- **CALI-1** Define the spec schema (typed Python + JSON serialization) — parameters, references, assertions, machine stub.
- **CALI-2** Measurement API: implement the MVP subset (§8) over trimesh + CadQuery, with tests against known parts.
- **CALI-3** Evaluator: parse `assert` exprs → `{pass, actual, margin}` report.
- **CALI-4** Generator: CadQuery script template + LLM authoring for the bracket family; build-error capture.
- **CALI-5** Intake: Claude call, intent → draft spec, clarify gate, human confirmation.
- **CALI-6** Loop controller: wire generate → build → sense → evaluate → decide; iteration cap.
- **CALI-7** Decide: route continuous failures → optimizer (one param), structural failures → LLM edit.
- **CALI-8** CLI M0: end-to-end one-shot on the bracket family.
- **CALI-9** Webapp M2: FastAPI + React/three.js viewer, spec editor, report panel, STL download.
- **CALI-10** References M3: STL intake as `role: fixed`, interference + clearance assertions.
