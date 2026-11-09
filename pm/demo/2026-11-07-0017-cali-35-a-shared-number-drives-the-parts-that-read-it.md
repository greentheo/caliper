### 2026-11-07 · A shared number drives the parts that read it (CALI-35c #3c)
1. With a key: plan a design of several parts (the turbine sentence), Build it, then say "make the mast 10 ft". The
   reply says "Changed mast top z from 7 to 10 ft. Rebuilt from it, with no new design: the mast, the hub." and what
   the design's checks measure now; the viewport shows the taller mast with the hub on it.
2. Each rebuilt part's history says "skeleton" with the change; its strength check reads "older version" until it's
   checked again.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_skeleton_drives.py` (stubbed: no key needed).
