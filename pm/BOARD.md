# Caliper board

Kanban of every task. One line per card: `CALI-N — title · priority · milestone`.
Full acceptance criteria in [`TASKS.md`](TASKS.md). Move cards between sections as state changes.

_Last updated: 2026-06-11_

## 🧊 Backlog
- CALI-1.M1 — Refinement loop · P1 · M1
- CALI-9 — Webapp · P1 · M2
- CALI-10 — References · P1 · M3

## 🔨 In Progress
- _(none)_

## ✅ Done — Milestone M0 complete 🎉
- CALI-8 — CLI (M0 end-to-end) · P0 · M0 · _2026-06-11 · `caliper run` produces a real STL, ALL PASS_
- CALI-4 — Generator (bracket family) · P0 · M0 · _2026-06-11 · builds watertight, 4×Ø5.2 holes_
- CALI-2 — Measurement API (MVP subset) · P0 · M0 · _2026-06-11 · mesh + B-rep holes verified_
- CALI-7 — Decide (route by failure type) · P0 · M0 · _2026-06-11_
- CALI-6 — Loop controller · P0 · M0 · _2026-06-11_
- CALI-5 — Intake (Claude) · P0 · M0 · _2026-06-11_
- CALI-3 — Evaluator · P0 · M0 · _2026-06-11_
- CALI-1 — Spec schema · P0 · M0 · _2026-06-11_
- CALI-0 — Project scaffolding · P0 · M0 · _2026-06-11_

> **M0 done:** loose idea → spec → real mesh → measured against spec → one iteration → downloadable
> STL. Full suite **47 passed**. Verified end-to-end via a pip CadQuery scratch venv while the
> conda/conda-forge env (the canonical dev env) finishes solving; re-confirm `make test` there once it lands.
>
> **Next milestone — M1 (one iteration cycle):** CALI-1.M1 — feed the report back to decide for a
> single NL refinement ("make the holes bigger spacing") + a single optimizer tune. Then M2 (webapp).
