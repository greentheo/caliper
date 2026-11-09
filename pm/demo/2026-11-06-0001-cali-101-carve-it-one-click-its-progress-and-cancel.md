### 2026-11-06 · Carve it: one click, its progress, and Cancel (CALI-101 #93)
1. **On a printed part with a strength check, the button says how long:** "at least about N min at this size" (after a carve has finished: "about N min …, as its last carve took").
2. **Click Carve it once:** one `POST /carve`. The button stays off. The panel shows "step k of 7: …", the bar, and
   "about N min left" once it has a pace. Click around the cards, or reload the page: the panel stays.
3. **Click Cancel:** "stopping at the next step…", then "Cancelled after k of n steps: what it finished is below",
   with the chart of the steps it finished. The Studies row says the same.
4. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_carve_click.py`.
