### 2026-11-13 · CALI-178 (#284) · #285's review: "Checked" only for what's measured; a flush seam's outside corner asks

The reviewer's item and the foreman's ruling on #285.

- **"Checked" only for what's measured (rule 6).** `joints.landed` used to say "Checked: … is now a bevel" on the strength of the `JOINTS` entry alone, over a square edge. Now:
  - **Measured:** a rabbet's or a dado's step (`joints.MEASURED`). "Checked: … is now a rabbet, 6 mm deep." A bevel's angle and a mortise come with #283's marks. That's still open, so here they're said as the entry only.
  - **Not measured:** any other kind reads "Its JOINTS entry now says bevel: the shape isn't checked here.", with `landed` None. Never a "Checked".
  - **Misses (✗, and the turn isn't a success):**
    - no step in the pieces ("Its JOINTS entry says rabbet, but the pieces show no step: neither runs into the other.");
    - an entry changed to another kind ("Its JOINTS entry now says dowel, not rabbet.");
    - an entry removed;
    - pieces that no longer touch;
    - an unchanged entry, as before.
  - **The shape line:** a landed rabbet no longer also says "Its shape didn't change (the same volume …)". The joined solid is the same, and its step was measured.
- **A flush seam's outside corner asks.** The top's end and the side's face are one face in the solid, so the seam between them is no edge; the edge nearest it is the top's outside corner.
  - **Before:** "make that a rabbet" there went to the designer, and the reply was ✓ with "couldn't tell".
  - **Now:** `joints.beside` sees the corner is on one piece, beside another it touches. The turn doesn't run the designer. It says "That edge is the top's outside corner, not where two pieces meet. The joint between the side and the top is where they meet inside: pick that inside corner, or name the pieces ("the joint between the side and the top").", and isn't a success.
  - **An edge with no joint near it** goes the ordinary way.

**Tests:** 4 new and 1 reworked (the landed table, now 5 rows), all failing on ee38aa8. 6 mutants, all caught.
- **Around run:** the 56 test files around these changes pass, and so do the 17 other guards that scan the source (`test_spatial` among them), so #283's CI miss isn't repeated here.
