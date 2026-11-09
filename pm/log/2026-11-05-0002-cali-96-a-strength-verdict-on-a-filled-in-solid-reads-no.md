### 2026-11-05 · CALI-96 (#78) · A strength verdict on a filled-in solid reads "not trusted yet"
- **Rule 6, found on the owner's step-stool-2 after the ship.** *What is it?* said `build()` was filled in, while
  *Will it work?* read "✓ Holds kid + dad (250 lb), 2 times over" from a check that ran on that block.
- `consistency.filled(store, pid)` (cached per version and script) now says when a part with `loads()` fails the
  volume check by being filled in. When it does:
  - both cards' strength lines read warn: "Not trusted yet: the strength check ran on a filled-in shape, not the
    step stool as built. Fix its shape first …";
  - the build book and the kids' book don't print a holding line;
  - a study on it says, in its record, notes and headline, that the number is the block's.
- Tests: `tests/test_filled_verdict.py`, written first and failing on main (the filled box read "Holds …, 3.1
  times over"). On the owner's design, read on a copy: main shows ✓, this branch shows warn on both cards.
  Commit: `53f1067`.
