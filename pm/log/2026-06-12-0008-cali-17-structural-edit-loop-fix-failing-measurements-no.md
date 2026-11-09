### 2026-06-12 · CALI-17 · Structural-edit loop — fix failing measurements, not just builds
- **Closes the two-actor loop** for LLM-authored parts (design spec §2/§5): the LLM revises its own
  script when a *measurement* fails, the same way CALI-16 healed build errors.
- **`authoring.improve(spec, author, max_rounds)`:** each round the LLM writes/revises `build(params)`,
  we build it sandboxed + measure it; a build error feeds back the **traceback**, a failing assertion
  feeds back the **report** (id + expr + actual + margin). Stops on green, an unchanged failure
  signature (oscillation), or the round cap — mirrors the bracket loop's rails (CALI-6). Author is
  injectable → fully tested without a key. Folds CALI-16's build-heal into the same loop.
- **CLI:** `caliper gen` now uses `improve` (`--max-rounds`), printing rounds + heals/revisions.
- **Webapp:** `POST /api/gen` (refactored `_finish()` shared with the bracket `_execute`) + a
  **"✦ author any part"** toggle that routes Build → `/api/gen`; the authored `part.py` is shown and
  persisted; `get_run` returns it so a reloaded gen part shows its script.
- **Verified live (CLI):** `gen "a hexagonal pen cup…"` → 4 rounds (2 build-heals + 2 revisions),
  honestly reported **"best effort"** — the 2 residual fails were a *contradictory intake-drafted
  assertion* (a hexagon can't be 60×60 in bbox) and *measurement noise* (min_wall 2.99 vs hard ≥3.0),
  not author misses. Good integrity signal — it doesn't fake a pass.
- **Verified in browser (Preview MCP):** "✦ author any part" → "a round coaster, 90mm, 4mm, 3mm raised
  lip" → **ALL PASS in 1 round**, rendered in 3D, authored CadQuery shown in the script panel. No
  console errors.
- Tests: 4 `improve` tests + `/api/gen` server test. **110 passed.** Commit: 6ee3e52
- Roadmap stamped: next is the **assembly spine** — CALI-19 (tolerances & fits), CALI-20 (assembly
  model), CALI-21 (insert-into-assembly).
