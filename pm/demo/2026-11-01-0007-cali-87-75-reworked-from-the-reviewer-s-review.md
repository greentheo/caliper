### 2026-11-01 · #75 reworked from the reviewer's review (CALI-87 #63)
1. **Name both sides of a box stool "side" and make a build package:** the kids' book is there, with "Add the
   first side", "Add the other side", and "touches both sides" on the top's page.
2. **Lighten a carved part:** refused straight away, telling you to say "roll it back" first.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_kidbook.py tests/test_release.py
   tests/test_carve_dropped.py tests/test_carve_stale.py tests/test_consistency.py tests/test_pictures.py`.
