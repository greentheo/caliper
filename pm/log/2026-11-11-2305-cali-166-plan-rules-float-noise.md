### 2026-11-11 · CALI-166 (#249) · Plan rules compare past float noise; the drive says what followed; three small words

The small follow-ups from tonight's reviews.

1. **Float noise, not a measuring tolerance.** step-stool-4's `top_at_height` failed after any change to 17 in: 17 × 25.4 =
   431.79999999999995 against 431.8.
   - The evaluator now compares two numbers with `math.isclose` (`REL_TOL = ABS_TOL = 1e-9`) for `==` and `!=`.
   - `<=` and `>=` are "less (or more), or close". Strict `<` and `>` stay strict.
   - A margin within the noise reads 0.
   - It's one rule for the plan's rules and a part's own.

   The foreman's call, over my first try at an absolute 0.01: the evaluator compares more than lengths, and
   `safety >= 2.0` must still fail at 1.995. Pinned: 17 in, `safety >= 2.0` at 1.995 and 1.99999, a weight by a
   thousandth, and counts. A real measuring tolerance belongs to the rule (`abs(top_z - 431.8) <= 0.5`), never the
   evaluator.
2. **The drive says what followed.** When a shared size moves a mirror through its source, the reply says "side_left
   follows side_right: both now 17 in."
3. **A mirror word about a feature isn't a part mirror.** "bolt holes mirrored to match the side flanges", "slots
   mirrored on both sides" and "the cut-outs are mirrored" give no "mirror, but not of which part" note.
4. **An older run's "not checked" gives one next step:** "this run is from before unseen walls were recorded: check it
   again." The hand check follows only where a re-run can't see the wall either (`too_thin`): "If it still can't see
   its walls, a hand check or a printed test piece is the way to know."
5. **An older run's trial doesn't claim an unseen wall.** It reads "no prediction: this run is from before unseen walls
   were recorded: check it again", and its basis is "from a run from before unseen walls were recorded".

#250 carries the two layout items (the re-frame on a resize, and the `narrowBy` and 701–1279 px pins).

**Tests:** 13 in `test_followups_249.py`. Nine fail on main; the rest pin what mustn't move. All 12 mutants are caught.
The 19 around-files pass (453), so no part assertion or plan rule there moved.
