# Caliper board

Kanban of every task. One line per card: `CALI-N — title · priority · milestone`.
Full acceptance criteria in [`TASKS.md`](TASKS.md). Move cards between sections as state changes.

_Last updated: 2026-09-18 (**M4**: CALI-28 Design object + CALI-29 chat turn handler shipped; see [`specs/caliper-conversational-spec.md`](../specs/caliper-conversational-spec.md))_

## 🎯 M4 — the design session (current milestone)
> The engine works; the UI is a control panel for it. M4 makes the product a **viewport + a conversation**.
> Decisions (Theo, 2026-09-18): chat-first on a **single part** before decomposition · old panel **demoted**
> to an Advanced drawer, not deleted · assertion promotion **proposed & confirmed**, never silent.

- CALI-30 — Feedback → assertion promotion (propose, validate, confirm) · P1 · M4
- CALI-31 — Streaming: job + SSE so the chat narrates long authoring runs · P1 · M4
- CALI-32 — Front end: viewport + chat as default; panel → Advanced drawer · P1 · M4
- CALI-33 — Clarify round → stored requirements (ask once, never re-ask) · P1 · M4

## 🚀 M5 — whole machines from one prompt (after M4)
- CALI-35 — Decomposition planner: prompt → assembly skeleton (parts + interfaces + asserts), reviewed before authoring · P0 · M5
- CALI-36 — Nested sub-assemblies (descend into a part that is itself a design) · P1 · M5
- CALI-37 — Feature-level selection (per-face export + face-id round-trip) · P2 · M5

## 🧊 Parked — engine breadth (pre-M4 backlog)
- CALI-24 — Optimizer-in-the-author-loop: let CALI-19b tune the authored part's continuous params (not just LLM revision) for coupled inserts · P2 · assembly-spine
- CALI-12 — Threaded holes done right (tapped/insert vs clearance; the machine uses tap-diameter today) · P2 · generator
- CALI-18 — `largest_through_bore` counts a tube's OUTER wall as a bore (both are cylinders); distinguish interior bores · P2 · measure (found authoring a grommet)
- CALI-11 — Variable bend angle (e.g. 45°) · P2 · generator
- CALI-12 — Threaded / tapped / insert holes · P2 · generator
- CALI-13 — Primitive & geometry library + multi-part assemblies · P2 · epic (story for later)

## ⏸ Blocked / waiting
- CALI-14 — SpaceMouse via NL-Proxy (driver coexistence) · P2 · M2 · _phase 1 shipped; phase 2 blocked on Theo's on-screen API telemetry_

## 🔨 In Progress
- _(none)_

## ✅ Done — Milestones M0 + M1 + M2 + M3 complete 🎉
- CALI-29 — Chat turn handler · P0 · M4 · _2026-09-18 · `chat.turn(store, message, scope)` — **scope is the selection** (unscoped = the design, scoped = the clicked part). Closes the real gap: **there was no code path to refine a part inside an assembly**. Revisions are handed the design context (siblings, mates, enforced assertions, feedback tail) on a *copy* of the spec, told to build in world coords, and **every change re-measures the WHOLE design** — the reply names what it broke, by id, with the number. Routing = Claude with a deterministic fallback that degrades instead of crashing, and **asks instead of guessing** when ambiguous. Added `revert` mid-task because the break reply offered a rollback the handler couldn't perform. A revision that never builds is never written. `caliper chat`. **Verified live**: widened a carriage (kept its world pose), then broke `carriage_clears_rail` at interference=7200 and got told, then rolled it back to green. 217 passed._
- CALI-28 — Design object + store · P0 · M4 · _2026-09-18 · **the M4 spine**: `designs/<slug>/` holds the **root prompt**, the **requirements clarified once**, a **part tree**, and per part a **feedback history** + a snapshot of **every revision**. It *is* an assembly underneath (sources relative to the design root), so `evaluate_assembly`/`assemble`/`insert` consume a design unchanged and **a one-part design is a one-part assembly** — no second code path. `write_part` snapshots + indexes + appends history in one step (history can't drift from the geometry) and **evicts the mtime-keyed build cache**, which would otherwise let a re-measure 'prove' the pre-change part. `adopt_run` pulls in existing runs; `prompt_context` builds the **distilled** (not transcript) context for a revision. `caliper design new|list|show`. 184 passed._
- CALI-27 — Hardening (Theo's reports) · P1 · M2 · _2026-06-13 · **fixed the partial-machine bug** (one failed part STL aborted the load loop → now parallel + per-part tolerant, error bar names what broke); `load_parts_tolerant` + `part_errors` on `/api/assembly`; build errors show the exception line, not boilerplate; **"❓ How this works" primer** + intent="one part" label + step-by-step Insert hints; README **"▶ Run it → http://127.0.0.1:8000"**. Verified in-browser incl. a deliberately-broken assembly. 158 passed._
- CALI-25 + CALI-23 + CALI-26 — A whole small machine · P1 · assembly-spine · _2026-06-13 · a 4-part **corner leg** (two solid 20×40 bars + gusset bracket + foot, M5s through aligned holes) → `caliper assemble examples/machine.yaml` ALL PASS incl. **bolt-hole alignment** measured at ~1e-15mm. **CALI-23:** assembly parts build from a `.py` CadQuery script at assemble time (B-rep kept). **CALI-25:** `holes_world`/`min_hole_misalignment` + `hole_misalignment(a,b)` probe. **CALI-26:** viewer shades colliding parts red; serves `.py` parts as STL. Verified CLI + in-browser._
- CALI-21c — Viewer UX · P1 · M2 · _2026-06-13 · fixed monitor/DPI resize (re-apply pixelRatio + CSS-fill canvas + DPR watcher), **middle-mouse pan** (CAD-style mouseButtons), and a **⤢ fit** button + `F` key with a **content-sized grid** (was a fixed 400mm plane). Left-click-only picking. Verified in-browser._
- CALI-21b + CALI-20b — Webapp insert UI + assembly viewer · P1 · M2 · _2026-06-13 · load an assembly in 3D, **click two parts to pick interfaces**, choose fit + intent, Insert → the LLM authors the bridge live, it renders green, the assembly re-measures. `/api/assemblies`, `/api/assembly/{id}`(+part STL), `/api/insert`. **VERIFIED LIVE in-browser** (Preview MCP): bridged two posts in 1 round at 0.21mm/side. Fixed a double-path-resolution bug. 153 passed._
- CALI-21 — Insert-into-assembly · P1 · assembly-spine · _2026-06-12 · **the north-star headline.** `caliper insert <asm> --between a,b --fit slip` — the LLM authors a part **in world coords** that mates to two named interfaces at a fit band, measured against the posed parts + no-collision, then it's added back to the assembly (run-dir source + fit mates) and re-measured. `insert.py` (`insert_spec`/`_bridge`/`insert_part`/`add_part_to_assembly`). **VERIFIED LIVE:** bridged a 50mm gap first try at 0.21mm/side. 148 passed._
- CALI-19b — Multi-parameter optimizer · P2 · assembly-spine · _2026-06-12 · `decide.tune_multi` jointly tunes N continuous knobs against a global objective (all_pass, #passing, worst margin, −change). Coordinate descent by default (eval-frugal); **escalates to seeded scipy `differential_evolution` only when CD can't reach feasibility** (the coupled case). `decide` route 0 fires with ≥2 knobs + a numeric fail. 142 passed._
- CALI-22 — Author-loop fit & refine · P1 · generator · _2026-06-12 · fit/refine of LLM-authored parts now **edit the real `part.py`** via `improve()` seeded with the existing script (`refit_authored` / `refine_authored`); no more "refuse authored" guard. CLI + `/api/fit` + `/api/refine`. 138 passed._
- CALI-20 — Assembly model · P1 · assembly-spine · _2026-06-12 · N parts + named **mates** (no_interference/clearance/fit/touch) + assembly assertions. `assembly.py` (Part/Mate/Assembly, YAML round-trip); N-body probes `pairwise_interference`/`max_interference`/`min_pair_clearance`; mates → measured assertions; reuses the single-part evaluator (margins, Report). `caliper assemble`. 134 passed._
- CALI-19 — Tolerances & fits · P1 · assembly-spine · _2026-06-12 · fit classes (press/snug/slip/free/running) → tunable clearance **bands**; two-sided band margins + iterative optimizer refine; `approx`/`within`/`fits` helpers; `fit --fit slip` & webapp dropdown; intake taught tolerant asserts. + guard: fit/refine refuse authored parts (no more silent bracket)_
- CALI-17 — Structural-edit loop · P1 · loop · _2026-06-12 · `authoring.improve` — the LLM revises its script to fix failing **measurements**, not just build errors (two-actor loop closed). In CLI (`gen`) + webapp (✦ author any part)_
- CALI-16 — LLM-authored generator · P1 · generator · _2026-06-12 · `caliper gen` — the LLM writes the CadQuery script (any part, not just brackets), run sandboxed, measured, self-heals build errors. Also fixed 2 LLM-intake bugs (prefill, schema-laxness)_
- CALI-10 — References (M3) · P1 · M3 · _2026-06-12 · import STL as `role: fixed`; real `interference` + `min_clearance`; `caliper fit` resizes a part **snugly** to clear a reference; + webapp gizmo fit UI_
- CALI-15 — Recent parts (browse / load past runs) · P1 · M2 · _2026-06-12 · list + click-to-load; fixed a hole-count parse that hung the kernel_
- CALI-9 — Webapp (M2) + SpaceMouse · P1 · M2 · _2026-06-11 · FastAPI + three.js viewer, refine loop, WebHID SpaceMouse_
- CALI-1.M1 — Refinement loop · P1 · M1 · _2026-06-11 · NL refine → re-derive → regenerate → re-measure_
- CALI-8 — CLI (M0 end-to-end) · P0 · M0 · _2026-06-11 · `caliper run` produces a real STL, ALL PASS_
- CALI-4 — Generator (bracket family) · P0 · M0 · _2026-06-11 · builds watertight, 4×Ø5.2 holes_
- CALI-2 — Measurement API (MVP subset) · P0 · M0 · _2026-06-11 · mesh + B-rep holes verified_
- CALI-7 — Decide (route by failure type) · P0 · M0 · _2026-06-11_
- CALI-6 — Loop controller · P0 · M0 · _2026-06-11_
- CALI-5 — Intake (Claude) · P0 · M0 · _2026-06-11_
- CALI-3 — Evaluator · P0 · M0 · _2026-06-11_
- CALI-1 — Spec schema · P0 · M0 · _2026-06-11_
- CALI-0 — Project scaffolding · P0 · M0 · _2026-06-11_

> **The single-part loop is complete.** loose idea → spec → **LLM-authored geometry** → measured →
> **revised until correct** → **dimensioned to a fit**. Two generators: the hardcoded **bracket**
> (`run`/`refine`/`fit`, offline + optimizer) and the **LLM author** (`gen` / ✦ author any part — writes
> the CadQuery itself, self-heals build errors AND failing measurements). Plus a **3D webapp** with a
> gizmo **fit-to-reference** UI and **fit classes** (press/slip/free…). Full suite **121 passed**
> (cadquery 2.7.0 / occt 7.8.1).
>
> **A whole small machine, measured green.** **CALI-25** ✓ — `caliper assemble examples/machine.yaml`
> builds a **corner leg** (two solid 20×40 bars + a gusset bracket + a foot, screwed with M5s) and proves
> it: 4 mates touch, nothing collides, and the **bolt holes line up** (a new `hole_misalignment` probe,
> measured at ~0). Parts are CadQuery scripts built at assemble time (**CALI-23**, B-rep kept → exact
> hole probes); the viewer shades collisions red (**CALI-26**). The measurement vocabulary grew to match
> the geometry — exactly the predicted bottleneck. See **TESTING.md** for the full walkthrough.
>
> **The headline is now clickable.** **CALI-21b/20b** ✓ — the webapp loads an assembly in 3D, you
> **click two parts to pick the interfaces**, choose a fit, and the LLM authors the bridging part live
> (it renders green; the assembly re-measures).
>
> **The north star is reachable end to end.** **CALI-21** ✓ — `caliper insert <asm> --between wheel,frame
> --fit slip` makes the LLM **author a part in assembly coordinates that mates to two named interfaces at
> a measured fit**, then adds it back and re-measures the whole assembly. **Verified live:** it bridged a
> 50 mm gap on the first try at 0.21 mm/side (dead centre of the slip band). This rides on **CALI-20**
> (N parts + named mates, `caliper assemble`), **CALI-19/19b** (fit bands + multi-param optimizer), and
> **CALI-22** (fit/refine edit the real authored `part.py`). The whole loop — idea → spec → authored
> geometry → measured → revised → *fitted into a larger assembly* — now closes. Next: make it **visual**
> (CALI-21b/20b webapp) and scale to **whole machines**. Complexity scales by *decomposition* into
> small, well-fit parts — and Caliper can now place a new one into an existing assembly.
