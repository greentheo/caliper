### 2026-11-19 · CALI-209 (#348) · the FEA judges each piece in its own material

The FEA judged a part of two sheet materials in one material: its most by volume, every voxel at that strength and
solved at that stiffness. Per-voxel material (CALI-82) only came in for wood with printed pieces. Measured both ways on
#328's synthetic box:
- **Over-credit:** an XPS floor in a mostly plywood box, resting on the ground (no plate check, so the FEA is the
  number), read ✓ 105× under 600 lb at plywood's 30 MPa. At its own 0.4 MPa it's 1.38×: a false ✓.
- **Under-credit:** a plywood floor in a box of XPS walls read 0.47× by the FEA at foam's strength. The plate check read
  9.18×.

**The fix:** `prepare` runs `_two_materials` for any part whose sheets and sticks are of more than one material, not
only wood with print.
- Each piece's voxels carry its own strength and stiffness.
- A voxel two pieces of different materials share is the weaker's, by strength, with its E.
- A voxel no piece claims is the printed material where the part is printed (CALI-82, unchanged). Where nothing's
  printed, it's the weakest of the part's materials, never the stronger (the foreman).
- The "Analysed as all …" note gives way to "Each piece in its own material: …".
- Wood of one material plus print reads exactly as before (`tests/test_mixed.py` unchanged and green).

**Pinned** (`tests/test_own_material_fea.py`):
- the XPS-floor box at 600 lb is ✗ at 1.4× or below, governed by the FEA in the floor, with the new note and not the
  old one;
- the plywood floor between XPS walls reads its FEA above 5 × 0.47 and holds;
- the map on six voxels: the shared voxel is the weaker's in either order, and the unclaimed ones are the weakest's.

**Fail first:** all three failed on main, for the reasons above (the floor held; 0.47; the map all plywood).

**Mutants** (each anchor once, scratch copy, the new tests plus `test_mixed.py`):
1. the own-material branch off: caught;
2. the last piece wins a shared voxel: **survived** at first (the test listed the foam last, so "last wins" was
   "weaker wins"). That was a gap in my test. It now runs in both orders and catches it;
3. an unclaimed voxel gets the strongest: caught;
4. E not set per piece: caught;
5. an unclaimed voxel left at the part's material: caught;
6. the "Analysed as all" note kept: caught;
7. the one-material shortcut dropped: **survived**. It gave the same dict as building from the key, so I dropped it from
   the code rather than test a no-op;
8. the stiffness not set for several materials: caught.

**Theo's designs** (copies, every part, main against this): every studied part reads the same, case by case, so nothing
goes ✓ → ✗.
- No studied part mixes sheet materials. The cargo box on the trailer does (a plywood floor, XPS walls, lumber sticks),
  but it has no `loads()`, so the load study doesn't run on it today.
- When it gets loads, its walls will be judged as bare XPS. Their fiberglass skins aren't credited, as on main, where
  the whole box was one bare material.
- hatch_swing fails to load the same way on both sides; it's not from this change.
