### 2026-11-15 · CALI-190 (#301) · "Pairs" only where each support runs most of the way across; short supports and uneven ones not checked by hand

The reviewer's clean check of the grouping raised a point for Theo's decision 5, and the foreman made it a safe-side default before he answers. Held both ways, "half each way" gives each pair half the load, so the pairs balance only half its moment. That holds where every support is a long joint across the piece: the rest of the moment goes along them, as on v7's sides and rails. On short supports (a ring of four posts), with the load at (90, 0), it read the near one at 0.475, where statics needs 0.9 or more.

- **Pairs are kept only where every support's joint runs most of the way across:** at least 3/4 of the piece's width along it (`MOST_OF_THE_WAY`, pending Theo with decision 5).
- **Otherwise:** "not checked by hand: its supports are short, so how the load splits isn't simple". Never the half share.
- **A support that runs most of the way across pairs across its own line.** A narrow, deep top on two sides and two rails is two pairs again; grouped by its farthest support, it had read as one row.
- **The words:**
  - "it rests on three or more supports in a row" only where they are in a line;
  - otherwise "it rests on more supports one way than the other": five supports (sides and three rails), or three in a triangle.
- **v7 is unchanged:** 3.28×, 5.75× and 8.7×, all three cases followed as chains. Its sides run the step's whole depth, and its rails 0.9 of its width.

**Tests:** the joint check, 66:
- the ring of four short posts at (90, 0), not checked;
- the same ring with long supports still paired (0.475 / 0.025 / 0.25 / 0.25);
- five supports, and three in a row;
- a narrow deep top as two pairs;
- three in a triangle.

**Mutants:** 4 of 4 caught (short supports pairing; uneven called a row; uneven both ways allowed; never pairing across its own line).
