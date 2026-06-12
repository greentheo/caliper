# Caliper board

Kanban of every task. One line per card: `CALI-N — title · priority · milestone`.
Full acceptance criteria in [`TASKS.md`](TASKS.md). Move cards between sections as state changes.

_Last updated: 2026-06-11_

## 🧊 Backlog
- CALI-9 — Webapp · P1 · M2
- CALI-10 — References · P1 · M3

## 🔨 In Progress
- _(none)_

## ✅ Done — Milestones M0 + M1 complete 🎉
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

> **M0 + M1 done.** loose idea → spec → mesh → measure → **NL refinement → re-derive → regenerate →
> re-measure** → downloadable STL. Full suite **61 passed** in the canonical conda env
> (`/opt/anaconda3/envs/caliper`, cadquery 2.7.0 / occt 7.8.1). `make test` / `make run` / `caliper
> refine` all work with zero config.
>
> **Next milestone — M2 (webapp wrapper):** CALI-9 — FastAPI around the library + React/three.js
> front end (intent box, live spec editor, 3D viewer, report panel, STL download). The demoable
> "YouTube moment". Then M3 (references: STL intake + interference/clearance).
