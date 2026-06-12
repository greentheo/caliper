# Caliper board

Kanban of every task. One line per card: `CALI-N — title · priority · milestone`.
Full acceptance criteria in [`TASKS.md`](TASKS.md). Move cards between sections as state changes.

_Last updated: 2026-06-12 (CALI-10 / M3 references shipped)_

## 🧊 Backlog
- CALI-11 — Variable bend angle (e.g. 45°) · P2 · generator
- CALI-12 — Threaded / tapped / insert holes · P2 · generator
- CALI-13 — Primitive & geometry library + multi-part assemblies · P2 · epic (story for later)

## ⏸ Blocked / waiting
- CALI-14 — SpaceMouse via NL-Proxy (driver coexistence) · P2 · M2 · _phase 1 shipped; phase 2 blocked on Theo's on-screen API telemetry_

## 🔨 In Progress
- _(none)_

## ✅ Done — Milestones M0 + M1 + M2 + M3 complete 🎉
- CALI-10 — References (M3) · P1 · M3 · _2026-06-12 · import STL as `role: fixed`; real `interference` + `min_clearance`; `caliper fit` resizes a part **snugly** to clear a reference_
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

> **M0 + M1 + M2 + M3 done.** loose idea → spec → mesh → measure → refine → STL, with a **3D webapp**
> (`make serve`) and now **fit-to-reference**: import an STL as `role: fixed` and `caliper fit` resizes
> a part until it clears it (`interference`/`min_clearance` measured exactly on meshes). Full suite
> **90 passed** in the canonical conda env (cadquery 2.7.0 / occt 7.8.1).
>
> **Next — CALI-13 (generator breadth, epic):** primitive & geometry library + multi-part assemblies.
> The assembly thread reuses CALI-10's interference/clearance substrate (now built) for *our own*
> generated parts, not just imported STLs. CALI-13 also scopes the first batch of new primitives to add.
