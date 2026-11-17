### 2026-11-16 · CALI-194 (#321) · a leg's end, read across it

The reviewer's re-check: a 10 mm hole, 25 mm deep, down the middle of each leg's end (a dowel's, a hanger bolt's pilot,
a hollow print) let the one ray up the hole and across a 3 mm gap to the top: a leg built short read as bearing, 2.93.
A false green.

The foreman's rule, now `_built_gap`:

- **Five rays** from 5 mm inside the leg toward the top: the centre, and four toward its corners at `RAY_AT` = 30% of
  its half-width along each side.
- **Only rays that start inside the solid count** (`spatial.contains`). The holed leg's centre ray starts in the hole,
  so its corner rays decide.
- **It bears if any counted ray touches** within `BEARS_MM`: the least gap. "Every" would read a rounded end short.
- **No counted ray** (a bore wider than the rays): "the back left leg's built end at the top isn't measured: no ray
  across it starts inside the solid". Not checked by hand, never read as bearing or short.

| leg end | built | reads |
|---|---|---|
| 10 mm hole | flush | bears |
| 10 mm hole | 3 mm short | declared flush, built 3 mm short: not checked by hand |
| 15 mm round | flush | bears |
| 18 mm round | flush | bears (its corner rays drop 1.2 mm: "every" read it short) |
| 24 mm bore | flush | not measured |

Tests: 5 new in test_posts. The holed-short and bore cases failed on the old source; the other three pin what already
read right. 6 mutants, all killed. The any/every one survived at first: a 15 mm round drops only 0.1 mm at 30%, so both
rules read it as bearing. The 18 mm round tells them apart, so it's pinned too.
