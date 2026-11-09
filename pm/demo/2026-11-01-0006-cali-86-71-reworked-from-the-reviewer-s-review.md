### 2026-11-01 · #71 reworked from the reviewer's review (CALI-86 #62)
1. **Record a test on the sample stool that broke at 150 lb:** both the design's and the part's *Will it work?*
   go red with "It broke at 150 lb in your test. We predicted it would hold 400." No ✓ is left above it.
2. **Record several steps, one sagging far more than predicted:** that step governs the line, even if a heavier
   one has no sag.
3. **A printed box:** "Holds a foot, about … times over." The rough-model note sits by the promise.
4. **An old carve run:** it reads "of the whole solid (carved before CALI-86 …)".
5. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_trials.py tests/test_answers.py
   tests/test_printed_strength.py tests/test_studies.py tests/test_samples.py tests/test_pictures.py`.
