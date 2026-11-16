### 2026-11-15 · CALI-190 (#301) · The lever rule by statics, a load past its supports included; three in a row not checked by hand

The reviewer found this in the first commit, older than A–D, and the foreman made it a must-fix under Rule 6. `_lever` used the lever rule only for two supports with the load between them, and took equal shares otherwise. So a load landing past its supports read half on each: with supports at 0 and 100, a load at 101 or 110 read 0.5 / 0.5. On the 20° splayed stool, loaded just past its right side's top, both tops read 250 lb, as if centred. A top loaded on its overhang read its near joint at half, and its far joint, which statics lifts, as pressed.

- **Two supports in a group: statics, signed.** The near support takes more than all of it and the far one is lifted, a negative share. Through `_route`, the lifted joint takes a pull (withdrawal), never bearing. At 101: −0.01 / 1.01; at 110: −0.1 / 1.1.
- **Three or more in a row:** "not checked by hand: it rests on three or more supports in a row". That case is statically indeterminate, so it's an honest gap, not a third each.
- **Side by side** (at the same place along the axis), they share equally, as before.
- **v7 is unaffected:** its loads land between its supports. It's still 5.75× down, and with 1% or 10% sideways.

**Tests:**
- the lever directly at 50, 95, 100, 101 and 110;
- three in a row at 190, not checked;
- the 20° stool loaded 2 mm past its right top: the right bears more than the 500 lb, and the left is pulled, not pressed.

**Mutants:** 2 of 2 caught (unsigned shares; three shared equally).
