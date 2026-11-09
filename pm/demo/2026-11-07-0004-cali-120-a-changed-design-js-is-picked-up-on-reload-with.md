### 2026-11-07 · A changed design.js is picked up on reload, with no ?v= to bump (CALI-120 #128)
1. View the page's source: `design.js?v=` is a hash of the file. Change `design.js` and reload: a new key, and the
   new script. `index.html` still says `?v=dev`.
2. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_cache_key.py`.
