### 2026-11-16 · CALI-194 (#321) · a leg's end bears where all its rays but one touch

The foreman: "any" was too loose. A dowel stub that reaches the top, with the leg's shoulder 3 mm short, reads rays
[0, 3, 3, 3, 3]. Under "any", the leg bore over its whole end at 2.93, where the stub alone is about 0.16.

The rule, in `_post`, reading `_built_gap`'s five readings (it gives each counted ray's now, not the least):
- **Bears** where all the counted rays but at most `BEARS_ALL_BUT` = 1 are within `BEARS_MM`.
- **Some touch, not that many:** "the back left leg touches the top at only part of its end". Not checked by hand.
- **None touch:** short, by its least reading, as before ("built 3 mm short" where it's declared flush).
- **No counted ray:** not measured, as before.

| leg end | built | rays, mm short | reads |
|---|---|---|---|
| 10 mm hole | flush | –, 0, 0, 0, 0 | bears |
| 10 mm hole | 3 short | –, 3, 3, 3, 3 | built 3 mm short |
| 15 mm round | flush | 0, 0.1 ×4 | bears |
| 18 mm round | flush | 0, 0.62 ×4 | only part of its end |
| 18 mm round | 3 short | 3, 3.62 ×4 | built 3 mm short (its least) |
| one corner notched 15 mm, 3 deep | flush | 0, 0, 0, 0, 3 | bears (all but one) |
| 10 mm dowel stub, 3 long | 3 short | 0, 3 ×4 | only part of its end |

**A correction.** I said earlier (on #321, and in 2026-11-16-1540) that the 18 mm round's corner rays drop about
1.2 mm. They drop 0.62 mm. My estimate took the round's corner as a sphere, and the test caught it. It's still past
`BEARS_MM`, so the 18 mm round reads as touching at only part of its end.

Tests: the stub, the short round and the notch are new; each ray reading is pinned. 8 mutants, all killed. At first the
notch and the short round weren't there, and three survived: "every", "bears only where all touch" and the most
reading for the least.
