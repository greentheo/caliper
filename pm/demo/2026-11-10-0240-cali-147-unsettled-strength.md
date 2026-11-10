### 2026-11-10 · The scorecard says when a strength number isn't settled (CALI-147 #191)
1. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_unsettled_strength.py`: a run too coarse to see its walls reads as not settled, with the reason, on the scorecard and in the build book, and a resolved run reads as it did.
