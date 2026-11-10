### 2026-11-09 · The Parameters panel (CALI-108 #108)
1. Open a one-part design, or select a part: **Parameters** is below the cards.
2. Click a number, type 3/8, Enter. "Rebuilds as v8" while it works, then "v8 written: set wall_t to 3/8 in by hand". The
   script's `wall_t` is exactly 9.525, the cards re-measure, no Claude call.
3. Type 9 in a field with a range: it says "Must be …" and Rebuild goes off.
4. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_params.py`.
