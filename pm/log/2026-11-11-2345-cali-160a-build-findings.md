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
