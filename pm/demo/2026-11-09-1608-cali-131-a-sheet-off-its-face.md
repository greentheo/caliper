### 2026-11-09 · A sheet off its face is named (CALI-131 #162)
1. On a part whose sheet outline isn't on the solid's surface, the design's checks fail with "seat top: declared 9.5 mm
   below where the part has it", and say what's being counted as printed until it's moved.
2. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_sheet_face.py`.
