### 2026-11-13 · CALI-180 (#286) · A joint check measures a bevel's angle and a mortise or notch; a two-distance chamfer says both

The foreman asked for this on 2026-11-13, once #283 and #285 had merged. It's numbered CALI-180 because the P1 #287 took CALI-179 first.

- **"Checked" covers a bevel, a through tenon and a notch.** `joints.MEASURED` adds them. They're read from `marks.of`, the same bevels and cuts the patterns, the cut list and the book are drawn from.
  - **A bevel:** "Checked: the joint between the back side and the top is now a bevel, 10° on the back side's edge." That's an edge of one piece cut at an angle to sit on the other.
  - **A through tenon:** "Checked: … is now a through tenon: a 3/4 in x 5 in mortise in the left side." A notch says "a 3/4 in x 5 in notch".
  - **Misses (✗, and the turn isn't a success):**
    - a bevel entry over square edges: "Its JOINTS entry says bevel, but neither edge is cut at an angle where the side and the top meet.";
    - no cut: "… but neither piece runs through the other: there's no mortise.";
    - the other cut: "… but the left side has a notch for the stringer, open at its edge, not a mortise.", or the reverse.
  - **Asking for it:** "mortise" and "mortise and tenon" now ask for a through tenon.
  - **Still said as the entry only:** a dowel, a pocket screw, a mitre and the rest ("Its JOINTS entry now says dowel: the shape isn't checked here.").
- **A two-distance chamfer says both (the reviewer's ask on #283).** A 15 × 6 mm chamfer read "15 mm (9/16 in) at 22°". Its two distances are now worked out from the depth and the angle, and said down the edge first, then in across the face.
  - **The cut list:** "side: chamfer 15 × 6 mm (9/16 × 1/4 in) along …", without the angle.
  - **The book:** "Chamfer the 1 edge marked C on the side, 15 × 6 mm (9/16 × 1/4 in), …".
  - **The page:** "…, on the other face: 15 mm down the edge and 6 mm in across the face."
  - **A 45° chamfer** reads as before: "12 mm (1/2 in) at 45°".
- **Done-when:**
  - "make that a bevel" on the inside seam under a splayed stool's top reaches the designer as that pair's entry, and comes back ✓ "Checked …, 10° on the back side's edge".
  - The tenoned stool's stringer checks as a 3/4 in x 5 in mortise in each side.

**Tests:** 8 new tests and a new row in the landed table (a square edge under a bevel entry is a miss). 3 were reworked: the unmeasured row and the unmeasured turn now use a dowel, and the kinds a request asks for gain "mortise".
- All 7 that test new behaviour failed on main. The turn test was written after the code, and the "bevel unmeasured" mutant shows it catches the old behaviour.
- **Mutants:** 15, all caught. Two survived at first (a bevel meeting anything; a mortise for any piece), so there are 2 more tests: a bevel elsewhere on the piece, and the step beside a side whose mortise is the stringer's, aren't that joint's.
- **Around run:** 91 files pass: slices C and D's around-files, plus every guard that scans the source.
