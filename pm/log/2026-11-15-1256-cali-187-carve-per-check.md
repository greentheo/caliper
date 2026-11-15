### 2026-11-15 · CALI-187 (#298) · Slice 0 measured against multigrid; CARVE_PER_CHECK 45 → 50

Theo, 2026-11-14: "6 hours to carve it, that seems like a long time, I wonder if we can do a faster solve there?" whittle#5 (multigrid) merged as `87c1470`. Slice 0 measures where a carve's time goes now. The numbers are posted on #298.

**How:** a probe in scratch wraps whittle's `VoxelFEA.solve` and times every solve, with its CG iterations, fallback, load cases and voxels, by phase: the check, the carve's sweep, its station checks. It ran on two scratch designs:
- step-stool-5 restored to v5, the printed stool: 147,641 voxels at 4.15 mm, 3 cases;
- `test_printed_strength`'s printed box at 30 lb: 77,708 voxels at 1.5 mm, 1 case.

The stool's check says v5 fails (1.75x, coarse), so the probe skipped the "already fails" refusal on the copy, for timing only. Niced, on a shared machine with load 5–7: ±20%.

- **Stool, multigrid:**
  - check 13.4 s; carve 1,005 s;
  - the sweep is 983 s of it: 82 solves of 3 cases, median 241 iterations, 12 s each;
  - the station checks are 16.8 s, for 2 steps.
- **Stool, Jacobi:** check 198 s. 10 sweep solves were measured at about 187 s each (about 15,800 iterations), so a full carve is about 4.7 h, which is Theo's "6 hours" on his loaded app.
- **Box:**
  - multigrid: check 3.9 s, carve 197 s (sweep 90%);
  - Jacobi: check 9.4 s, carve 1,260 s.
- **What it means:**
  - Multigrid is about 15× on the stool.
  - The sweep is 90–98% of a carve now, and the station checks are 2–6%. So slice 1 (caliper's parallel station checks) could save at most about 6%; not built, the foreman to decide.
  - The sweep's solves need about 80 iterations a case against the check's 23. That, and a solve's 3 cases in parallel, are whittle's levers.
  - Slice 3 (the coarse sweep) would take about 8× more off.
  - The box carves differently past step 4 under multigrid and Jacobi (BESO near-ties). Each step is still checked on its own.

**`CARVE_PER_CHECK`:**
- **The ratio rose:** under multigrid a carve took 51× its check (box) and 75× (stool; about 79 with all 7 steps). The check got faster than the sweep.
- **Set to 50:** both carves took at least that, and the card says "at least about".
- **Tests:** `test_job_limit`'s estimates (60 s → 50 min; 600 s → 8.3 hours, past the limit; 430 s within it, 433 s past it) and `test_make_it_better`'s 20 s → 17 min were changed first, and failed on 45. The around run (30 files) then failed two more `test_make_it_better` pins of "45 min" (60 s × 45), which were the tests' fault: they're 50 now.
