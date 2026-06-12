# Caliper board

Kanban of every task. One line per card: `CALI-N — title · priority · milestone`.
Full acceptance criteria in [`TASKS.md`](TASKS.md). Move cards between sections as state changes.

_Last updated: 2026-06-11_

## 🧊 Backlog
- CALI-10 — References · P1 · M3
- CALI-11 — Variable bend angle (e.g. 45°) · P2 · generator
- CALI-12 — Threaded / tapped / insert holes · P2 · generator
- CALI-13 — Primitive & geometry library + multi-part assemblies · P2 · epic (story for later)

## 🔨 In Progress
- CALI-14 — SpaceMouse via NL-Proxy (driver coexistence) · P2 · M2 · _owner: claude · phase 1_

## ✅ Done — Milestones M0 + M1 + M2 complete 🎉
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

> **M0 + M1 + M2 done.** loose idea → spec → mesh → measure → refine → STL, now with a **3D webapp**:
> `make serve` → http://127.0.0.1:8000 → intent box, 3D viewer (three.js), measurement report, refine
> box, STL download, and **3Dconnexion SpaceMouse** (WebHID). Full suite **71 passed** in the
> canonical conda env (cadquery 2.7.0 / occt 7.8.1).
>
> **Next milestone — M3 (references):** CALI-10 — import an STL as `role: fixed`, add interference +
> min_clearance, iterate a part to fit it (the FEA-free Stage 2 loop). Generator-breadth epic CALI-13
> tracks new primitives + multi-part assemblies for later.
