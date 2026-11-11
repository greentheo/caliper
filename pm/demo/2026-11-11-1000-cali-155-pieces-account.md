### 2026-11-11 · Pieces that don't account for the solid (CALI-155 #219)
1. Offline: `PYTHONPATH=src python -m pytest tests/test_pieces_account.py`. A designer that writes flat strips is told where the sides are, and a right sloped declaration passes.
2. Open a part whose `construction()` leaves a panel out: the 3D view shows the solid, the tree says why, and the card offers no patterns, cut list or weight.
