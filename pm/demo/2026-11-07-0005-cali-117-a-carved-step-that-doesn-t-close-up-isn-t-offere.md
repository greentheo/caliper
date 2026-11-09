### 2026-11-07 · A carved step that doesn't close up isn't offered (CALI-117 #105)
1. Carve a printed part (**Carve it**). Every step offered rebuilds into a closed solid; one that wouldn't reads
   "Can't use this step: its carved shape doesn't close up into a solid…", and its Carve button is off.
2. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_carve_closed.py`.
