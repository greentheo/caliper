### 2026-11-13 · CALI-180 (#286) · #289's review: a mortise or notch lands only where the outline has it; "Checked" stands where "Not measured" stood

The foreman accepted #289 with one round.

- **One test of a cut, from the outline.** On a scratch copy of step-stool-5 v3, "make that a mortise" on the stringer seam read ✗ "the left side's outline has no hole where it goes", and then "Checked … a 3/4 in x 6 in mortise".
  - **Why they disagreed:** `_marked` read the cut off the marks, from where the pieces cross. #275's `mortises` rule (`_host_mortises`) reads the declared outline, which is what the router cuts.
  - **Now `joints._cut_in` reads it the way #275 does.** A mortise lands only where the host's outline has the hole. A notch lands only where the outline is cut round the piece: the piece then lies outside the outline, so the crossing is found against the outline's convex hull (`joints._hull`).
  - **The solid alone is partial ("!"), with what's missing:** "The solid has the stringer through the left side, but the left side's outline has no hole there yet: cut the mortise into the left side's outline." The notch says "… in the left side's edge, … no notch there yet: cut the notch into …".
  - **On Theo's copy,** `joints.landed` now gives exactly that, with `landed` "partial", for "the bottom stringer through the left side".
  - **The marks' cuts aren't read for this any more.** They leave out a cut the outline already has, so a mortise done right would have read as no mortise.
- **A landed joint's "Checked" line takes the place of "Not measured: whether that's what you meant …"** in the reply, above the part's own checks, not at the end. That's `chat.refine_part`, the same place that drops "Its shape didn't change".

**Tests:**
- **New:** a mortise only in the solid (partial), as `landed` and as a turn ("!" first, no "Checked"); the notch in the solid only; the fixtures' cut sides.
- **Reworked:** the landed mortise and notch now have the hole and the notch in their outlines; both turn tests check where "Checked" stands, and that it's said once.
- **Mutants:** 9, all caught. A tenth found a branch that can't run: an outline is always counter-clockwise in its own frame, so the hull needs no turning round, and the branch is gone.
- **Around run:** 115 files pass: slices C and D's files, every guard that scans the source, and every test file that drives the chat.
