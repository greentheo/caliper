### 2026-11-01 · CALI-84 (#58) · One rule for where a load lands
- **Found in the walkthrough:** Theo's printed two-step stool passed `loads_land`, then its strength check said the
  foot "pushes on thin air". The foot's box was at the top's height, 1.2 mm above the floor of the 1/8 in mat
  recess. `loads_land` passed anything within about 2× the measuring tolerance, while the strength check reached
  one voxel. So they disagreed, both ways, depending on the voxel size.
- **Now one rule:** `load_study.touches(mesh, box, reach)`: the box is in the part, or within
  `reach = max(voxel, tolerance)` of its surface, with the voxel size from `study_spacing()` exactly as the study
  uses it. `loads_land` and `prepare` both ask it, and a miss fails both in the same words (which load, how far
  from the nearest surface). The strength check grows a box by reach plus half a voxel, so whatever passes has
  voxels under it. `held()` boxes use the same rule, and the authoring sandbox now reads `held()`.
- **Verdicts unchanged** on STOOL, BOX_STOOL and MIXED at 2 and 4 voxels through. The FEA moved ≤ 2.6% in safety
  and ≤ 4% in sag (2 vs 4 voxels through differ by 30–50%). `loads_land` on a printed part costs about 0.1 s more
  (it measures the thinnest wall for the voxel size).
- **On Theo's stool:** the adult's foot now lands. The child's box on the "lower step" really is in the air: the
  script's lower step is a box inside the upper body, so it adds nothing. Both checks now say so.
- Tests: `tests/test_load_lands.py` (12, written first and failing on the old code: the recess case passed
  `loads_land` and then raised in `prepare`), plus the strength suites. Commit: `06bd8db`.

---
