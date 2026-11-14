### 2026-11-14 · CALI-182 (#292) · A slant past 45° and a free-edge rebate are said, never drawn as a square edge

From #291's review. A full-thickness slant at 50, 60 or 70°, and a rebate along a free edge (10 down × 40 across), read as nothing. The patterns, the cut list and the book then showed a square edge, and it would have been cut square.

- **A slant past what a saw tilts to (`marks.SAW_MAX_DEG`, 45°) is marked S.** Each sheet edge's cut is now sorted by angle:
  - 2° to 45° is a saw bevel, as before;
  - steeper, up to 88°, goes into the new `slants`.

  "Slant: the edge marked S is cut at 60°, past what a saw tilts to (45°): plane or router it, or cut it at 30° from the other face." The cut list says "side: slant 60° along 17 11/16 in of edge, past what a saw tilts to (45°)", and the book has the same words. Never "Set the saw".
  - **How a full-thickness slant is found:** the corner reader (#290) used to drop a slant reaching the whole thickness. Now it hands it on, and the slant is placed the way a bevel is.
  - **On the page,** its line on the other face is dashed and its outline is drawn on the shown face, as a bevel's is (`_faced` takes both). `joints.landed` reads slants as well as bevels: a side splayed 48° still checks as that joint's bevel.
  - **S, not D:** D1, D2 already name the dados on the same pages.
- **A rebate along a free edge is marked R** (`marks._rebate`).
  - **How it's found:** rays come in from outside the edge face at 24 depths across the thickness. They meet a square part and a wall set back for the rest, which is one step at one face, the same at three points along the edge. A ray straight down onto its floor gives the depth. Something in front of the edge, a slope, or all-square means no rebate.
  - **How it's said:** "Rebate: 10 × 40 mm (3/8 × 1 9/16 in) along the edge marked R, on the other face, with a router or table saw: 10 mm down the edge and 40 mm in across the face; the dashed line is its wall." The cut list says "side: rebate 10 × 40 mm (3/8 × 1 9/16 in) along …", and the book says "Cut the rebate along the 1 edge marked R on the side, …, with a router or table saw."
- **Theo's designs:** on scratch copies, all 14 scripted parts have the same bevels, chamfers, slants and rebates as on #291's branch: none new.

**Tests:** `tests/test_slants_and_rebates.py`, 15 cases. The first 14 failed on #291's branch:
- slants at 50, 60 and 70°, said and drawn;
- 20, 40 and 45° still saw bevels;
- four rebates: 10 × 40, 10 × 5 and 6 × 12 on the far face, and 9 × 20 on the outline's own face;
- square edges still nothing;
- the 48° splayed joint;
- and, added for a mutant, an edge cut 50° for half its length and 70° for the rest, which isn't said as one slant.
- **Mutants:** 20. 19 are caught, once the two-slant edge was added. The one that survives is the rebate's square-part check, a guard: the wall's flatness and the floor's depth already reject every shape it would.
- **Around run:** 66 files pass: slice C's around-files, every guard that scans the source, the joint, remove and wide-chamfer tests, and the new file.
