### 2026-11-05 · A filled-in part isn't trusted to hold (CALI-96 #78)
1. **Open a copy of `step-stool-2`:** *Will it work?* reads "Not trusted yet: the strength check ran on a
   filled-in shape …" on the design and on the part. Say "fix its shape to match its pieces" and it clears.
2. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_filled_verdict.py`.
