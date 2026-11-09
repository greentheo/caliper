### 2026-10-30 · CALI-80 (#48) · Record the test: predicted against measured
- Showcase 1 (#10): "Dad stands on it, then sandbags go on until it breaks. Record the predicted vs measured here."
  Also the first real point for calibration (#42).
- **`trials.py`:**
  - **The prediction**, from the latest strength check on this version: for the worst load, the sag at the
    middle of the panel it's put on, at each step (50 lb at a time) up to where it should break, as a range.
    The range runs from the FEA's sag (joints solid: the stiff end) to the plate check's (edges free: the
    flexible end), linear in the load.
  - **What to measure it with:** the stool's top under 200 lb should sag 0.003–0.005 in (0.08–0.13 mm). A tape
    measure won't see that, so it says to use a dial indicator, or a straightedge and feeler gauges.
  - **The record:** each step in `trials/<part>.jsonl` (load, sag, broke, note, the version).
  - **On the card:** "Tested: it held 400 lb, sagging 0.006 in (we predicted 0.004–0.008 in)." or "Tested: it
    broke at 1,100 lb (we predicted about 1,240)." A test of an older version reads as stale.
- **Test it** under *Will it work? → the numbers*: what to do and with what, a chart of the predicted band with
  the measured points and where it should break, the step table, and a row to record a step.
  `GET/POST /api/designs/{slug}/parts/{pid}/trial`.
- Tests: `test_trials.py` (the prediction from the load to where it breaks, as a range, and what to measure with;
  none without a check on this version; steps kept and compared, the card's line, where it broke, an older
  version's test reads as stale; the API).
- Commit: `b957193`. PR #51.
