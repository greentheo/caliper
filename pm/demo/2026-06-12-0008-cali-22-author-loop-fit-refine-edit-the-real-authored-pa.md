### 2026-06-12 · Author-loop fit & refine — edit the real authored part (CALI-22)
**New:** `fit` and `refine` now work on **LLM-authored parts** (the ones with a `part.py`). They no
longer rebuild a bracket / refuse — they route through the author loop **seeded with the existing
script**, so the LLM revises the real part to clear a reference or apply a plain-language change.
**Try it — CLI** (needs `ANTHROPIC_API_KEY`):
```bash
caliper gen "a 50x30x6 mounting plate with an 8mm hole"        # → runs/run_00NN (writes part.py)
caliper fit runs/run_00NN --ref bolt=examples/obstacle.stl --fit slip   # LLM revises part.py to fit
caliper refine runs/run_00NN "add a 4mm chamfer on the top edge"        # LLM edits the real part
```
**Try it — browser:** `make serve` → "✦ author any part" → build → drop in a reference, pose it, **Fit**
(or type a change in the refine box). Both now edit the authored script instead of erroring. The header
reports the rounds + heals/revisions, same as `gen`.
