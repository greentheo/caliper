### 2026-11-06 · Asked for, changed, measured (CALI-107 #107)
1. **On a part, say "make the wall 6 mm":** the reply starts "Asked for: make the wall 6 mm", then "Changed: wall 4 mm →
   6 mm", "Measured: its volume went from … to … cm³", and what isn't measured. Then "The part's own checks pass."
2. **Ask for something the designer can't fit:** the round fails, naming the line of any `try/except` or clamp that
   would have skipped it quietly. If nothing changed, it says the shape didn't change.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_fallbacks.py`.
