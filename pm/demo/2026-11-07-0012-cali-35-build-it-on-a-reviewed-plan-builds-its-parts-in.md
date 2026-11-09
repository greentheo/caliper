### 2026-11-07 · Build it on a reviewed plan builds its parts, in order (CALI-35 #3b)
1. With a key, plan the turbine ("…a 7 ft mast…, for a generator I already have"), review it, and press **Build it**:
   the base, then the mast, then what goes on it, one at a time, each narrated as it's built with its checks between
   parts ("The mast: built (mast_height ✓)"); the generator is yours, not designed.
2. A part that won't build stops there: the ones before it stay, and **Build it** again carries on from it.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_build_plan.py`.
