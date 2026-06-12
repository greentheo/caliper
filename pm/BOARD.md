# Caliper board

Kanban of every task. One line per card: `CALI-N — title · priority · milestone`.
Full acceptance criteria in [`TASKS.md`](TASKS.md). Move cards between sections as state changes.

_Last updated: 2026-06-11_

## 🧊 Backlog
- CALI-1.M1 — Refinement loop · P1 · M1
- CALI-9 — Webapp · P1 · M2
- CALI-10 — References · P1 · M3

## 🔨 In Progress
- CALI-2 — Measurement API (MVP subset) · P0 · M0 · _mesh side verified; B-rep holes pending OCCT env_
- CALI-4 — Generator (bracket family) · P0 · M0 · _written; pending OCCT env to verify build/holes_
- CALI-8 — CLI (M0 end-to-end) · P0 · M0 · _gate verified; one-shot smoke pending OCCT env_

## ✅ Done
- CALI-7 — Decide (route by failure type) · P0 · M0 · _2026-06-11 · optimizer + structural routes verified_
- CALI-6 — Loop controller · P0 · M0 · _2026-06-11 · converge/cap/oscillation/build-fail verified_
- CALI-5 — Intake (Claude) · P0 · M0 · _2026-06-11 · offline drafting + clarify gate verified_
- CALI-3 — Evaluator · P0 · M0 · _2026-06-11_
- CALI-1 — Spec schema · P0 · M0 · _2026-06-11_
- CALI-0 — Project scaffolding · P0 · M0 · _2026-06-11_

> Note: CALI-2/4/8 carry OCCT-dependent acceptance (real CadQuery build + hole detection + CLI
> smoke). Code is written and the non-OCCT logic is green (39 passed, 4 skipped); these flip to Done
> once the conda/OCCT env finishes building and `make test` runs the 4 skipped CadQuery tests.
