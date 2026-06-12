# Caliper board

Kanban of every task. One line per card: `CALI-N — title · priority · milestone`.
Full acceptance criteria in [`TASKS.md`](TASKS.md). Move cards between sections as state changes.

_Last updated: 2026-06-12 (CALI-19 tolerances & fits shipped; single-part loop complete)_

## 🎯 Next shift — the assembly spine (do these three)
- CALI-20 — Assembly model: N parts + named mates/interfaces + assembly-level assertions (generalize CALI-10 to N bodies) · P1 · assembly-spine — _the heart of the north star_
- CALI-22 — Author-loop fit & refine: route fit/refine of LLM-authored parts through `improve()` (seeded from part.py) so they edit the real part, not a bracket · P1 · generator (guarded now; the bug Theo hit)
- CALI-19b — Multi-parameter optimizer (nevergrad/scipy): joint tuning of N continuous params for coupled fits · P2 · assembly-spine (1-D + iterative-refine shipped in CALI-19)

## 🧊 Backlog
- CALI-21 — Insert-into-assembly: author a new part against two named interfaces at a target fit · P1 · assembly-spine ("insert a support between the wheel and the XYZ assembly") — _needs CALI-20 + CALI-22_
- CALI-18 — `largest_through_bore` counts a tube's OUTER wall as a bore (both are cylinders); distinguish interior bores · P2 · measure (found authoring a grommet)
- CALI-11 — Variable bend angle (e.g. 45°) · P2 · generator
- CALI-12 — Threaded / tapped / insert holes · P2 · generator
- CALI-13 — Primitive & geometry library + multi-part assemblies · P2 · epic (story for later)

## ⏸ Blocked / waiting
- CALI-14 — SpaceMouse via NL-Proxy (driver coexistence) · P2 · M2 · _phase 1 shipped; phase 2 blocked on Theo's on-screen API telemetry_

## 🔨 In Progress
- _(none)_

## ✅ Done — Milestones M0 + M1 + M2 + M3 complete 🎉
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
> **Next — the assembly spine:** **CALI-20** (assembly model: N parts + mates + assembly assertions, the
> heart), **CALI-22** (author-loop fit/refine so authored parts are fully editable), **CALI-19b**
> (multi-param optimizer for coupled fits). Together they reach **CALI-21** — "insert a support between
> the wheel and the XYZ assembly." The lesson from the phone stand: complexity scales by *decomposition*
> into small, well-fit parts, not by one ever-bigger monolith.
