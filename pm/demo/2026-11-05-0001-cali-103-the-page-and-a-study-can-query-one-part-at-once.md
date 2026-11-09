### 2026-11-05 · The page and a study can query one part at once (CALI-103 #95)
1. **Start a carve, then revise the part and click around the cards while it runs:** the app stays up, and a card
   comes back in about a second.
2. **Kill the server mid-carve:** the Studies page then shows that carve as "not finished: k of n steps checked".
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_spatial.py`. Its raw race crashes a subprocess on
   purpose, and the locked one survives.
