### 2026-11-06 · CALI-97 (#100 review) · Four across, a budget for the finer run, and a ✗ stays a ✗
The reviewer's 5 findings and the foreman's 10 items on #100.
- **`RESOLVE_MIN` is 4** (the foreman's call from #100's own table; still NEEDS ENGINEER CHECK for #42).
- **A finer run is capped by a voxel budget:** `finest()`, 8× the default's voxels (`FINER_BUDGET`, twice as fine
  each way). An asked-for `spacing_mm` finer than that runs at the finest it may, and says so. Where even that can't
  get 4 across the wall, no finer run is offered, and the card says: "Not checked: its walls are too thin for the
  voxel check at this size. A hand check or a printed test piece is the way to know."
  - **Judgment call:** the review said "the same budget" as the default. With `VOXELS_THROUGH` 4 = `RESOLVE_MIN` 4,
    a default run is only unresolved when that budget already bound it, so a finer run inside the same budget could
    never be offered. 8× keeps the button meaningful and bounded. `FINER_BUDGET = 1` is the other reading.
- **The wall that gates a verdict is the thinnest** (the reviewer's blocker on d82c67e). A 10th percentile let 5 mm
  voxels "see" a spool hung from a 0.6 mm neck and call it ✓ 9.7× at 10 lb (main: ✗). Back to `min_wall_thickness`;
  where the thinnest spot is only a lip (the bar stool's 0.3 mm), the cap says "not checked", the safe side.
- **A ✗ stays a ✗,** with "The fail may be the model's: the voxels can't see its … walls." on the part card, the
  design card and the Studies row. Only a ✓ turns to warn.
- **Walls in a unit that doesn't round them away:** 1/32 in fractions, or mm under 1/32 in ("0.3 mm", never "0 in").
- **The numbers panel:** amber "not resolved" / "not checked" badges in place of a green "holds", in the case, the
  run's header and the run picker; the case says "The FEA read Nx at voxels of …, too coarse to see its … walls".
- **The finer run's time** comes from the run's own FEA time per voxel, scaled as voxels^(4/3): measured on the tube
  and the box stool, time per voxel grows as about the cube root of the voxel count.
- **No time for a finer run when the coarse run didn't connect** (the reviewer: "about 1 min" on the bar stool copy, for
  a run that took 39): its FEA stopped at once, so its time says nothing. The button reads "(how long: unknown)".
- **The spacing clamp is pinned by an assert:** an asked-for 0.1 mm reaches the voxelizer as the finest the budget
  allows (whittle's LoadStudy stubbed, so a mutant fails on an assert, not by running away).
- **Run ids sort by `created`** (`runs.newest_first`), the id as tiebreak, in every listing (loads, carve, lighten,
  aero, frames, gussets, whittle, patterns, cut plans) and in a saved sample. This was the reviewer's
  `test_resolved` flake.
- **The teardown judges only its own test's jobs** (a snapshot at setup); `CALIPER_JOB_GRACE` sets the wait.
- **The API's 0.1–50 mm bound is pinned** (the reviewer's surviving mutant now fails).
- **On the 0.01:** the id sort can't explain it. That test reads `study()`'s return value, never a listing. See #100.
- Tests: `tests/test_resolved.py` (the spool; the `across` allowance and an 8× budget that really binds: two
  mutants that survived), `tests/test_run_order.py`, `tests/test_jobs.py` (the reviewer's three-test leak, under
  pytester).
