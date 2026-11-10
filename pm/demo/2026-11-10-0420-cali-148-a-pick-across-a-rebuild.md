### 2026-11-10 · A pick doesn't outlive the rebuild it came before (CALI-148 #196)
1. Pick a face or an edge, change a number under Parameters and Rebuild: the pick's chip goes and the bar says to click it again.
2. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_pick_scope.py`.
