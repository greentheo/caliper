### 2026-11-14 · CALI-180 (#286) · #289's last round: a notch is a pocket, not a corner; a stick's joint is couldn't tell, never an error

The foreman's last round on #289.

- **A notch is a pocket the outline flanks on both sides** (`joints._flanked`).
  - **The false "Checked":** a piece resting in a concave corner of a stair-cut side lies outside the outline and inside its convex hull, so the hull read it as a notch: "Checked: … is now a notch: a 3/4 in x 5 5/8 in notch in the side".
  - **Now** the outline has to be there on both sides of the crossing, just past the piece's own faces (its thickness, plus 2 mm or a quarter of it), along at least half its run.
  - **An open corner reads ✗:** "Its JOINTS entry says notch, but the tread rests in a corner of the side's outline: it isn't cut round on both sides, so there's no notch." The same goes for "make that a mortise".
  - **The stool notched at its foot** still reads "Checked".
- **A stick's joint is couldn't tell, never an error.** `landed` raised `KeyError: 'polys'` on the cargo box's floor-and-rail seam. A pair with a stick in it now reads "Its JOINTS entry now says through tenon: a stick's cut isn't checked here.", with `landed` None, for every measured kind.
  - **`chat.refine_part` guards the call:** the part is written by then, so a check that breaks is said as `joints.NOT_MEASURED` and the turn goes on.
- **A sweep over scratch copies of Theo's 8 designs:** every joint in every part, checked as a through tenon, a notch and a bevel. Nothing raised, and no cut read "Checked".

**Tests:** 5 new in `test_joint_picks.py`: the stair stool as a notch and as a mortise, a floor-and-rail stick as both, and a `landed` that raises inside a turn. 7 mutants, all caught.
- **Around run:** 115 files pass: slices C and D's files, every guard that scans the source, and every test file that drives the chat.
