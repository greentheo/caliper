### 2026-11-14 · CALI-181 (#290) · A chamfer wider across the face than down the edge is marked

From #289's review (reviewer-2). Chamfers drawn 6 down × 15 across, 4 × 12 and 14 × 30 got no C mark, no cut-list line and no book line.

**Why:** #283's reader fires rays out through the edge face at three depths, and finds a chamfer only where the middle one hits the slant. That's a chamfer running further down the edge than across. A wider one leaves the middle of the edge face square. The 14 × 30 one puts the slant so close that the middle ray's hit falls short of its window. Either way, the edge read as "nothing to mark".

- **`marks._corner_chamfers`:** where #283's reader finds nothing, rays go in at each corner of the edge, along the bisector between the edge face and the board's face. One flat slant is a chamfer when it's:
  - the same three points along the edge;
  - flat, the same plane at ±0.5 mm either side;
  - neither face itself.

  Its two distances come from where that plane meets the edge face (down the edge) and the board's face (in across it).
- **Either way round, it's marked where one distance reaches past half the board's thickness.** A 6 × 15 is marked as much as a 15 × 6, and goes to the router or block plane, never the saw: "Chamfer the 1 edge marked C on the side, 6 × 15 mm (1/4 × 9/16 in), with a router or a block plane". On the page it's "6 mm down the edge and 15 mm in across the face".
  - **Left to the drawing, as before:** a 3 × 3 or 3 × 8, and a square edge.
  - **Also left to the drawing:** a deep round-over (r 17, not flat), a slant that grows along the edge (4 × 10 to 8 × 20, one plane but no one router setting), and a 70° slant the whole thickness (neither a saw setting nor a chamfer).
- **The ones #283 already read** (15 × 6, 12 × 12) are read the same way, by the same path.
- **On scratch copies of Theo's 8 designs,** every part's marks are the same with and without the new reader: no new chamfer, no changed bevel, nothing raised.

**Tests:** `tests/test_wide_chamfers.py`, 17 cases on boards drawn with explicit polylines, so no distance comes from CadQuery's argument order. The 4 cases that test the new reading failed on #289's branch; the others pin what already held.
- **Mutants:** 11. 10 are caught, after 4 more tests: the deep round-over, the slant that grows along the edge, the 70° slant, and a free-edge rebate (10 × 40, #291 review). The rebate catches the square-corner check: without it, its rays divide by a zero slope. A twisted, lofted chamfer failed the flatness check first, so a flat tilted one is what reaches the taper check. The one that survives is a guard with no behaviour a test can reach: the far-hit limit (another piece well past the corner isn't read).
- **Around run:** 64 files pass: slice C's around-files, every guard that scans the source, `test_joint_picks` and the new file.
