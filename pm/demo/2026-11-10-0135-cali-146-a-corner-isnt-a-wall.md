### 2026-11-10 · A corner isn't a thin wall (CALI-146 #189)
1. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_wall_skims.py`: a plate with near-square windows reads its thickness, and a real thin web beside a corner, a tapering sliver and a knife edge still read thin.
