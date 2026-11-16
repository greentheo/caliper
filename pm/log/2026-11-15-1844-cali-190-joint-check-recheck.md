### 2026-11-15 · CALI-190 (#301) · #311 re-check: a tie's one tension; modes against the face; an unplaced tie named; nearest the foot pinned

The reviewer's re-check of #311's rework was clean on its four items and found two Rule 6 points and two untested corners. The foreman made the two must-fix, and all four go in while #311 waits on Theo's five values.

- **A. A tie carries one tension, so each end gets the larger** (`demands`). Each splayed foot's thrust had gone into its own end. Under a load toward the right foot that read 9 lb at the left end and 93 lb at the right, so an end with fewer screws would read greener than it is. Now both ends read the larger. Pinned off centre, at 120 mm.
- **B. Modes are read against the face a joint bears on** (`_face`: the face piece's normal, from the edge into it), in `split` and `_route` both. They had been read against the edge piece's own direction. On a 20° splayed side's top, the push down its line read 266 lb, all bearing. Against the step's face it's **250 lb bearing and 91 lb across, in the screws**. Pinned at 20°; the 10° pin now reads 250 + 44. On square joints the two directions are the same, so v7 is unchanged: 5.75× down, 1% and 10% sideways.
- **C. A tie it can't place is named, never read as no tie.** A splayed stool whose stringer runs through notches in its sides (v7's arrangement) reads "its tie, the stringer, isn't checked by hand: its joints are notches (CALI-192)", not "nothing ties its splayed sides".
- **D. "Nearest the foot" is pinned:** a stool with both a stringer at the foot and a rail partway up. The stringer takes the thrust and the rail carries none. Switching to the highest tie had passed every test.

On #301, Y510 Table 3 is quoted with its column headings and footnote (1), so 53 psi reads as the S-1/S-2 dry column (exterior glue); S-3, interior glue, is 48.

- **Tests:** `tests/test_joint_check.py`, 46 tests.
- **Mutants:**
  - this pass: 4 of 4 caught (each end its own pull, the edge's direction, the unplaced tie unnamed, the highest tie);
  - the earlier sets, re-run: all caught, the two splay ones re-pointed at their new lines.
