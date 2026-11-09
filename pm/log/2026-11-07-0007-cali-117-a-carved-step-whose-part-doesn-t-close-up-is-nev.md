### 2026-11-07 · CALI-117 (#105) · A carved step whose part doesn't close up is never offered or adopted
- **What it was:** with #106's front-edge foot, and on main's own carve-down test once BLAS ran on one thread (#121's
  CI), the carve picked a step whose adopted part wasn't watertight. Which voxels a run carves follows the summation
  order, so it came and went; a fresh run here was watertight at every stage (station, wood, join, STL reload).
  A part that isn't watertight can't be voxelized, so the check adopting it runs fails or reads wrong.
- **Now:** each step's mesh is repaired if a fill closes it (`carve._closed`: merge, drop degenerate faces, fill holes,
  fix normals) and otherwise marked `closed: False` with why. The step offered is the lightest that holds **and**
  whose part, as adopting it builds it (`carve._adopted`: the wood as drawn joined to the carved print), closes up;
  one that doesn't is marked and the next is tried. `adopt` refuses a step that doesn't close (`carve.NotClosed`, a
  422 with the reason) and checks the STL as it will be read back; nothing is written for it. The panel shows "Can't
  use this step: …" and its Carve button is off. design.js v=56.
- `tests/test_carve_closed.py`: a small hole filled and a big one not; every carved step forced to leak (not offered,
  adopt refused, nothing written); a join with the wood forced to leak (a small gap repaired and adopted watertight,
  a big one refused) and the study not offering it.
- **#124 review, the cause:** a **pinch**. Where two surfaces of the carved part meet along an edge, the adopted
  shape keeps two vertices at one point apart by index: watertight in memory, and once merged (any STL round trip)
  four faces share an edge and it isn't (#105's 6,011 vertices, 12,060 faces). `_closed` judged the in-memory form,
  so the study offered step 2 and `adopt` refused it. Now `_closed` judges a merged copy, as it reads back, so offer
  and adopt agree; a pinch isn't something a fill mends, so that step is marked. `_offer` builds the script once.
  Tests: a pinch along an edge (closed in memory, refused merged; one meeting only at a corner reads back closed),
  and #105's repro (MIXED with its edge foot, 40 lb, 4 steps to 0.6): the step offered adopts, watertight
  (`slow`: several minutes).
