### 2026-11-11 · CALI-155 (#219) · Pieces that don't account for the solid

Theo's first real build, a plywood step stool, came out as two floating boards. The solid was right, with two splayed sides, but `construction()` declared each side as a flat strip inside the top panel. The view, "Patterns ready" and the weight all went from those strips, and the card's advice ("fix the shape") would have deleted the real sides.

A correct sloped declaration (its four real corners in 3D, on either face) passes every check, so a right answer wasn't being rejected. The round did fail on the strips, but it named the middle of the part between them, and when four tries ran out the last was kept.

Now: the round names each panel-shaped lump of material no piece describes, and how to declare it. The guide says a sloped panel's outline is its real corners in 3D. Where pieces leave a panel out (under 90% of the surface on a piece, and the rest panel-shaped) the view draws the solid and says why, and there are no patterns, cut plan, build package, weight or cost from them. The advice says to fix the pieces. A filled-in block or a lid left off isn't this: their pieces are still right, and both fixes stay offered.

A tipping case with no weight crashed the card ("unknown" isn't a card status); that's fixed too.

Before and after on every sample and on copies of Theo's designs: only the old copy of `step-stool-3` changes. Checked in a real browser on that copy. The 90% is the foreman's to set. Tests: `tests/test_pieces_account.py`, all mutants caught but one that is redundant with the cut plan's own refusal, which a test now tells apart. The whole suite is CI's.
