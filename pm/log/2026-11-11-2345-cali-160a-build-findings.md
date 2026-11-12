### 2026-11-11 · CALI-160 (#238) slice A · After a plan's build, what's measured wrong, as a list

After step-stool-4's first build, every part had built and they still didn't go together. All of it was visible once every part existed, and none of it to a designer writing one part at a time. A plan's build now ends with what Caliper **measured** wrong, with no model call (`review.py`). Each finding names its parts, says what's wrong in the person's words, and proposes the change:
- **a plan rule or mate that fails.** A pocket's fit gives its play ("the stretcher has 19.1 mm of play in side_left's pocket"). A touch that misses gives the gap ("the stretcher doesn't meet side_left: 9.5 mm apart"), and an overlap its volume.
- **a pair the plan calls mirrored** (its `mirror_of`, or "a mirror of side_left" in what it says) whose shapes differ by more than 1%, by `mirrors()` (#239): "Make side_right the mirror of side_left". A mirror made by flipping isn't checked: it's one by construction.
- **a part that sets its own copy of a shared size** (#240's `skeleton.shadows`).
- **a number the person stated that no part and no check reads**, so nothing measures it.

The list says it's measured and that there's no model reading yet. An empty one reads "nothing found in N checks. That's what the checks see, not that it's right: look at it." The build's result carries `findings` for the page's slices C and D.

On a stubbed step-stool-4 v1 (2×4 pockets, walls 15 and 12 mm, a plywood stretcher sitting in the pocket voids), it lists both pocket misfits, the mirror mismatch and the left-side miss.

This branch stacks on #240 and has #239 merged in, since it uses their measures. Slices B to D wait on Theo's three questions in the issue. Slice A runs automatically after a plan's build (recommendation 1), and only on plan builds.

**Tests:** 6 in `test_build_findings.py`, all stubbed, real geometry.

**Checks.** 6 tests in `test_build_findings.py`, one updated after #243's rework (the shadow finding needs the same size word). All 8 mutants are caught; the flipped-mirror skip, which survived at first, is pinned as not measured. The around-files (build plan, first build, show-it-first, first run) pass (87).

**After #243 merged and #246's rework.** Main and #246's branch are merged in. The mirror finding now reads `mirrors()` in mm, as #246 measures it: a pair the plan calls mirrored is a finding when its surfaces are more than 0.2 mm apart in place ("their surfaces are up to 41.6 mm apart"). The PR now targets main. 198 around-files pass.

**Rework from the review (the foreman's three).**
1. **Every mounted or touching pair gets a fit check, planned or not.** For a pair with no `fits_in` mate, `measure.pocket` runs both ways.
   - Where one goes into the other, the fit is measured at 0.3 mm a side.
   - Where neither does, nothing is listed.
   - Where it can't tell, it says "not measured: whether the stretcher fits side_left's pocket".
   - A part that lines up with a pocket but ends at its mouth, or a little short (step-stool-4's stretcher), is measured at the pocket's mouth: stepping in until walls close round its line. A hole the part's section doesn't fit across, such as a bolt hole under a side, isn't a pocket.
   - **On a scratch copy of Theo's v1** (his plan predates #243, so it has no `fits_in`), both pockets are now listed: "has 19.1 mm of play in side_left's pocket, and is 12.7 mm too big for it the other way", and the same for side_right. The stretcher's miss of side_left and the sides' mirror mismatch are still there.
2. **A measurement that errors is "couldn't measure", in words, with no exception's name and no fix.** It's said apart under "Not measured", and the count says so: "12 of 14 checks measured". A fit's fix follows the finding: "Size the pocket" for play or too big, "Move it down into the slot" for a part off it.
3. **A stated number counts only when a rule reads it.** One a part only names in its PARAMS is a note ("you said stretcher z is 100 mm; the side left names it, but no check measures it"). A stated length or height named for a part is measured on it ("you said stretcher length is 508 mm, and the stretcher is 384 mm long").
4. **Smaller:**
   - More ways to say mirror ("mirrors side_left", "a mirror image of the left side"); a mirror of nothing named is a note.
   - A rule finding says its why, not its expression.
   - `said` drops its unused `inches`.

15 tests in the file; all 9 of the rework's mutants are caught. Theo's v1 isn't pinned as itself, since that would put his own part scripts in the repo; the fixture is his plan's shape (no `fits_in`, the stretcher flush at each mouth).
