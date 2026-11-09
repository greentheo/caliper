### 2026-11-05 · A ✓ needs an FEA fine enough to see the wall (CALI-97 #80, reworked from #100's review)
1. **On a printed part whose walls the default voxels can't see (4 across, RESOLVE_MIN):** *Will it work?* reads
   "Not resolved yet: the check was too coarse to see its 5/32 in walls. Check it again finer." Under *the numbers*
   the badge reads **not resolved** (amber), never a green *holds*, and **Check it again finer (about N min)** runs
   it within the voxel budget.
2. **On one too big for its walls (the bar stool):** no finer button. It reads "Not checked: its walls are too thin
   for the voxel check at this size. A hand check or a printed test piece is the way to know."
3. **A fail on coarse voxels stays a ✗:** "Doesn't hold …, and it needs 2. The fail may be the model's: the voxels
   can't see its … walls."
4. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_resolved.py tests/test_run_order.py tests/test_jobs.py`.
