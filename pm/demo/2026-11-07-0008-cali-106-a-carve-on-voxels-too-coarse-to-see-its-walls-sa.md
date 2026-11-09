### 2026-11-07 · A carve on voxels too coarse to see its walls says so (CALI-106 #101)
1. Carve a thin printed part (**Carve it**): where the check couldn't see its walls, the steps that hold are amber dots
   reading "not resolved", and **Carve it like this** is off, saying why.
2. Theo's bar stool (a copy): **Carve it** is off, saying where and what to change: "Can't carve it by strength: its
   0.25 mm walls around z 16.1 in are too thin for a 0.4 mm nozzle to print and for your rule shell_wall_thickness
   (at least 2.85 mm): thicken them to that. For a strength carve, walls must be at least 9.2 mm at this size, so
   check it by hand or with a test piece instead." It stays off after a carve is cancelled, and a refusal never
   reads "ValueError: …". The card and the page give the same wall number (0.25 mm, not 0.2 and 0.3).
   **Lighten it** on a run too coarse to see the walls says "Not resolved yet…", as Studies does, not "Nothing
   lighter still holds".
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_coarse_steps.py`.
