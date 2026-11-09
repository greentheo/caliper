### 2026-11-05 · CALI-97 (#80) · A ✓ can't rest on an FEA too coarse to see the wall
- **Rule 6, found on Theo's bar stool:** "✓ … 2.58x", governed by the FEA at 4.6 mm voxels across a 3.9 mm printed
  wall.
- A study now records its thinnest wall and whether the FEA resolved it: 2 voxels across, for now (NEEDS ENGINEER
  CHECK; #42).
- When an unresolved FEA governs, both cards read warn: "Not resolved yet: the check was too coarse to see its 4 mm
  walls. Check it again finer." A button runs it finer, at least 2 voxels across, and says roughly how long.
- The design card's strength lines say "about" when the printed model governs.
- **Before and after, on the printed fixtures:** only the 1-voxel-across verdicts change (✓ → warn).
- **For #42:** the printed box reads ✓ 2.7× at 2 voxels across and ✗ 1.9× at 4, so 2 is too few to trust a verdict.
- Tests: `tests/test_resolved.py` (main reads ✓ on both cards for the coarse tube). Commit: `caf174e`.
