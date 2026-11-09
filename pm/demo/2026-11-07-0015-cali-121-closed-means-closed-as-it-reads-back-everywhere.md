### 2026-11-07 · "Closed" means closed as it reads back, everywhere (CALI-121 #133, #134)
1. Build a part whose shape doesn't close (two blocks meeting only along an edge): the build's reply says "⚠ Its shape
   isn't closed near z … mm: strength, weight and carving can't be checked until it is", at the edge where they meet.
2. Its weight reads "not checked: its shape isn't closed near z …", and whittle refuses it, saying where.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_closed_everywhere.py`.
