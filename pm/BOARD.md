# Caliper board

Kanban of every task. One line per card: `CALI-N — title · priority · milestone`.
Full acceptance criteria in [`TASKS.md`](TASKS.md). Move cards between sections as state changes.

_Last updated: 2026-10-28 (**M4 complete** in the browser + whittle bridge (CALI-31/32/33/38); see [`specs/caliper-conversational-spec.md`](../specs/caliper-conversational-spec.md))_

## ✅ M4 — the design session (complete)
> The engine works; the UI is a control panel for it. M4 makes the product a **viewport + a conversation**.
> Decisions (Theo, 2026-09-18): chat-first on a **single part** before decomposition · old panel **demoted**
> to an Advanced drawer, not deleted · assertion promotion **proposed & confirmed**, never silent.

- _(all shipped — CALI-28…33 + CALI-38, see Done)_

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

## ✅ Done — Milestones M0–M3 + M4 (the design session) complete 🎉
- CALI-44 — The box carries itself: walls as structure, fiberglass skins · P1 · M5 · _2026-10-28 · a part declares **`shell()`** — its walls as deep sandwich beams — and the frame study solves them with the tubes (whittle-agent added per-member material + Timoshenko shear); skins checked at their strength or wrinkling stress, foam shear by Caliper, fixing forces reported. **Fiberglass** skins in the materials (cloth + epoxy in the BOM). Theo's picks applied: drag **design 2**, **X-only** frame, **50 lb** aboard, box moved in to **3 in behind the bumper** (hatch rule retired, bumper rule ≥ 2 in). Hitch: **3,428 lb·in standing** (was 7,963 with 100 lb at 18 in). Walls strong (PMF ≥ 6.9×, glass ≥ 5.7× wrinkling-limited); counting them routes the roof's weight to the X's tips, so the frame isn't lighter — **47.7 lb, 4.46×** (2 in solid shank sets the floor)._
- CALI-43 — The frame carries the box as built; an X under the floor · P1 · M5 · _2026-10-28 · a frame study can carry the design's other parts **as they're built** — every panel, post and payload pound spread where it sits (`load_points`), landed on the nearest tube that carries the floor as **whittle point loads** (added by the whittle-agent; members stay whole so buckling is checked over the real length). Frames name **what-if layouts** (`LAYOUTS`); the panel picks one, compares runs, and names the **hardest-worked welded joint** (what a gusset carries). Frames weigh **as cut** (one length where a tube runs straight through, unless a bigger tube is in the way). Theo's X frame (2 in spine, 1 in X to the corners, 1 in edges, 3/16 gusset), box 58.9 lb + 100 lb on the floor: **no layout reaches 3.5×** — the 2 in shank in the receiver governs at its solid-bar limit (~2.2–2.4×); lightest at that limit is *X only* at **64.7 lb**; 1 in X needs the edges (78.9 lb). Receiver ~8,000 lb·in standing loaded, ~4,000 empty._
- CALI-42 — Room for the mattress: keeps and the part's own ranges · P1 · M5 · _2026-10-28 · box widened to **77 × 40 in** (a twin inside 1 in walls); above a full-width base the sides lean (tumble, shoulder), the front rounds off (nose) and the back tapers. A part declares **`keeps()`** (what it holds — the mattress) and **`RANGES`** (how far a study may search); whittle keeps the outside out of the keep, Caliper re-checks every design and shows the keep in the viewport. Drag study (8 numbers, behind the Leaf): **22 lbf ≈ 4.4 kWh/100 mi saved at 9% volume**, the mattress untouched; the curvier box is lighter too (52 lb vs 59)._
- CALI-41 — What it's built from: weight, balance & a shopping list · P1 · M5 · _2026-10-27 · a part declares `BUILD` (choices) + `construction()` (sheets, sticks, coverings, lumps) against a shared materials table; Caliper weighs it piece by piece, finds its **centre of gravity**, and makes a **bill of materials** (sheets packed on 4×8s, cuts on 8 ft sticks, canvas/glue/paint for PMF). Frames weigh in from `members()`. **Weight & balance** puts the design together: on Theo's camper, box **56 lb** (⅜″ ply 22, PMF 15, foam 10, posts 5) + 2″ frame **72 lb** → **4,774 lb·in** on the receiver standing still — the frame is the bigger half. Pickers try other choices without saving; *Use these* writes BUILD. Shape signatures now ignore construction, so drag studies still apply._
- CALI-40 — Size the frame · P1 · M5 · _2026-10-27 · whittle's FrameStudy on the tubes a part declares (`members()`+`supports()`): stress, sag, **what the hitch holds**, and a sweep to the lightest tubes that pass, written back into PARAMS. On Theo's frame: as drawn 1.45x, best 3.32x at 63 lb (ladder slimmed, steel moved to the jog) — and **6,400 lb-in on the receiver standing still** vs ~2,450 for a typical Class II, whatever the tubes. Fixed on the way: author token cap (2k→8k, truncation named), `body_count` counting sealed tube bores as bodies._
- CALI-39 — Parametric aero loop · P1 · M5 · _2026-10-27 · **a shape comes back as numbers, not a mesh.** Agreed with the whittle-agent session: whittle's new `ParametricStudy` searches the part's `PARAMS` against its drag model (with the **car as an obstacle** now — shelter that actually works), Caliper builds every candidate on a **warm sandboxed worker** (0.13 s vs 1–2 s cold; ~720 builds in 3 min) and writes the chosen numbers back into the script by AST position — the part stays parametric, comments intact. Every part is now authored **tunable** (PARAMS). Live on the hitch box: a ~16° boat tail, **11 lbf ≈ 2.2 kWh/100 mi saved**, envelope exact. On branch `cali-39-parametric-aero`; needs whittle `a1248d1` (`physics-and-slider`)._
- CALI-38 — whittle bridge · P1 · M4 · _2026-10-27 · Caliper drives Theo's **whittle** over its local JSON API (no whittle changes): send a part with the setup pre-filled, stream progress, file every station with the design, **bring one back** as the part's revision (script survives; roll back returns to it). **Carve the tail only** for a part riding behind something. Removal **measured** against the part (whittle's stations are voxel remeshes ~½ voxel larger — found live), growth reported on bring-back, savings in **kWh/100 mi**. Dropped after a live test: a frozen car stand-in in the same upload makes whittle carve nothing — needs obstacle support in whittle._
- CALI-31 + CALI-32 + CALI-33 — The design session in the browser · P1 · M4 · _2026-10-27 · **The home page is now a viewport + a conversation** (old panel at `/classic`). Click a part to talk about it; inspector shows size (in/mm), rules, history, whittle. Chat turns run as **jobs streamed over SSE** with per-design write locks (no lost updates). New designs open with a **bounded clarify round** whose answers become permanent requirements (blanks recorded as *assumed*). Inches shown when you speak inches; geometry stays mm._
- CALI-30 — Feedback → assertion promotion · P1 · M4 · _2026-09-18 · **the idea M4 rests on**: measurable feedback becomes a **test**, enforced forever by the existing evaluator. `promote.py` drafts (LLM, with deterministic patterns under it), **validates by actually evaluating** against current geometry — a probe that doesn't exist or an expr that throws is never offered — parks it in `pending.json`, and the **next turn** accepts or declines. Two levels: a one-part rule → the part's `spec.assert` (author loop enforces it), a cross-part rule → `assembly.assertions` (checked when anything changes). Unmeasurable feedback phrased as an obligation is **labelled**, not faked. `turn()` short-circuits on a parked proposal so "yes" isn't misread as a geometry request. **The live run drove two fixes**: promoted design rules are now **visible to the author** (they were enforced but unseen — the author then moved a part to 4mm instead of not at all), and a proposal that doesn't hold now says **the change didn't achieve what you asked**. Plus **conflict detection**: a rule contradicting one you locked in is named, and accepting retires it. 265 passed._
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
