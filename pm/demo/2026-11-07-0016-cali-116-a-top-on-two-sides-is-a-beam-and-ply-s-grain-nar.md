### 2026-11-07 · A top on two sides is a beam, and ply's grain narrows it (CALI-116 #118)
1. Open a stool whose top rests on its two sides, run **Will it hold?**, and open a case.
2. **Beam check** — "it rests on two opposite edges, 14.0 in apart: a beam across them … Cut with its face grain running
   across the gap and it's about 2.0 times over instead of 1.2 (on 6.8 in: with the grain along the span it's less
   stiff across, so less of it carries the load)". The verdict is the second number, as before.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_orthotropic.py`.
