### 2026-11-07 · The carve-through-the-API test allows a slow runner (CALI-121, #134 follow-up)
1. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_mixed.py -k carving_through_the_api` waits up to 25 min
   for its carve job (it took 13 on a loaded machine). Nothing to see in the app.
