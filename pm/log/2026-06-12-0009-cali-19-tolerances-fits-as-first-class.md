### 2026-06-12 · CALI-19 · Tolerances & fits as first-class
- **Why now:** the phone-stand failure (user-reported) was mostly *bad assertions*, not bad geometry —
  a contradictory `slot_fits_phone: 8 <= bbox.dx <= 12` (the part is ~75 mm wide; `bbox.dx` is the whole
  part, not the slot) + measurement noise (`min_wall 2.99` vs a hard `≥3.0`). The fix is a fits/tolerances
  vocabulary, not a smarter prompt alone.
- **`tolerance.py`:** printer-friendly **fit classes** (press/snug/slip/free/running) → `(lo, hi)`
  clearance bands (FDM ~absolute). Helpers `approx(x, nom, tol)`, `within`, `fits(clearance, kind)` bound
  into the evaluator namespace.
- **Evaluator:** two-sided band margins — `lo <= x <= hi` now yields a signed margin (distance to the
  nearest bound) so a fit band is **tunable** (was `None`). **Optimizer:** `tune_continuous` gains
  progressive refinement (4 shrinking rounds) to converge onto a narrow 0.2 mm band; `decide` skips the
  snug `prefer` for band targets so they centre in the band.
- **Surfaces:** `caliper fit --fit slip [--nominal]` + a webapp **fit-class dropdown** → a band
  assertion. Intake taught to prefer `approx`/bands over `==`/hard thresholds and to **never** assert an
  internal feature (slot) via `bbox.*` (the phone-stand bug, at the source).
- **Verified live:** `fit --fit slip` tuned a bracket **60 → 41.8 mm** → clearance **0.188 mm**, centre
  of the slip band. Browser dropdown wired + no console errors.
- **Also fixed the fit bug they hit:** fit/refine now **refuse LLM-authored parts** (part.py present)
  with a clear message instead of silently rebuilding a bracket — CLI + `/api/fit` + `/api/refine`.
  Proper fix (route through the author loop) tracked as CALI-22.
- Tests: `test_tolerance.py` (8) + band-margin + fit-class loop + authored guards. **121 passed.**
  Commit: 7d237cf
