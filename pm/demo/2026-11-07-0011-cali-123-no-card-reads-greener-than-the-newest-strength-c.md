### 2026-11-07 · No card reads greener than the newest strength check (CALI-123 #138)
1. Open the bar stool (a copy of Theo's): the design card's *Will it work?* says "✗ Holds a 250 lb person sitting…:
   last checked on v4: 1.7x, needs 2x · v7 not checked yet", as the part card does; no "2.58x" from the v1 card.
2. The Score panel reads "Scored as of v1:", each old pass an amber "·", each number "(as of v1)"; Score it again.
3. The history's v3 strength checks say "not checked: nothing connects where it's pushed to where it's held", not
   "doesn't hold, 0x".
4. The first open of the cards takes about 45 s on the stool (each printed piece sliced once), the next a few seconds.
5. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_newest_run.py`.
