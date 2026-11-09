### 2026-06-12 · Fits & tolerances — target a fit class, stop fighting noise
**New:** ask for a **fit** (press / snug / slip / free / running) and Caliper tunes the part until the
clearance lands in that band — "fits" as a first-class idea, not a magic number. Plus tolerant
assertion helpers (`approx`, `within`, `fits`) so a 0.01 mm measurement wobble no longer fails a check.
**Try it — CLI:**
```bash
make run INTENT="a 60 mm corner bracket for 2020 with four M5 holes"      # → runs/run_00NN
caliper fit runs/run_00NN --ref obstacle=examples/obstacle.stl --fit slip
# → constraint "0.12 <= min_clearance(obstacle) <= 0.3"; the bracket resizes (60 → ~41.8mm)
#   until clearance ≈ 0.19mm — centre of the slip band. Try --fit press / free / running too.
```
**Try it — browser:** `make serve` → build a bracket → open **“Fit to a reference (M3)”** → import an
STL, place it → pick a **fit** class from the dropdown → **Fit ▶**.
**Also:** fitting/refining an **LLM-authored** part now shows a clear message instead of silently
rebuilding a bracket (the bug from before) — full author-loop fit is tracked (CALI-22).
