### 2026-11-11 · CALI-163 (#241) · An edit that names several parts changes each, and says which it didn't

Theo's step-stool-4 message ("make both sides the right side; the stretcher doesn't fit snug; neither slot is sized off the stretcher") went to side_left only, and the reply opened "✓ revised side_left → v2".

- **Routing by the request, not the selection.** An `Intent` carries `parts`, every part the change names, in the design's order.
  - Claude's router is asked for them ("both sides", "neither slot", "all the legs", "the stretcher and the left side"), and an unknown one is refused.
  - Offline, `named_parts` finds several only when the message says several: a word they share (both/neither/each/all, or a plural), or names joined by "and" or a comma. With a shared word, the parts named outright come too.
  - A part named only as a reference ("make the carriage clear the rail") still routes to one part, as before.
  - A selected part doesn't narrow a message that names several.
- **Each part is revised on its own, in order, built and checked before the next.** The designer is told which one this revision is for ("This revision is to side_left only: side_right and stretcher are revised on their own"). A revision that hands a part back as it was writes no version.
- **The reply says first what changed and what didn't.** For example: "! Changed side_left; side_right not changed: the revision left it as it was." "✗ Nothing changed" when none did. A ✓ only when every part named changed and nothing broke. A request to mirror says it can't be done yet (#239) and gets no tick.
- **"Still measures green" says what was measured:** "The design's checks pass (touch, no overlap); whether a part fits snug in its pocket isn't measured." That stays until #240's `fits_in`.

**Tests:** 15 in `test_several_parts.py`, all stubbed. Two existing tests pinned the old green line and are updated. 140 targeted routing and turn tests pass. Mutants wait until Theo's live session on 8011 is done.

**Rework from the review (the foreman's six):**
1. **A part named as a reference stays out.** Offline now does what the router prompt says.
   - A group word ("both", "neither", "each", "every", "all") brings in only the parts it groups, and names join only by "and" or a comma.
   - A bare plural is the target only when no part is named outright.
   - Theo's message now gives side_left and side_right, not the stretcher. "Make the top thicker so the legs don't wobble" and "the top overhang the sides" give the top alone.
2. **Plurals group only true siblings.** These are ids that leave only position words or numbers once the stem is out (side_left, leg_front_left and shelf_2 qualify; corner_bracket_left and lid_hinge don't). A position word beside the plural narrows the group ("front legs" gives the two front legs), and -ves and -ies are made singular ("shelves").
3. **Rule 6:**
   - Theo's own wording counts as a mirror request: "both sides the right side", "use the left side for both sides", "the same as", "match", "like the other". It gets the not-yet-possible line (#239) and no ✓. This applies on the several-parts path only, since "make the hole match the bolt" on one part isn't a mirror.
   - A part counts as changed only when a number in its PARAMS moved or its volume changed. A comment-only edit writes no version and reads "not changed: no number moved and its shape didn't change".
4. **The second designer is told what the first part became:** "Already revised for it: side_left h 10 → 60."
5. **The count is said up front** ("revising 2 parts: side_left, side_right"), then "(1 of 2)", "(2 of 2)" as each starts.
6. **The pick is kept.** It goes with the part it was made on, the selected one.

36 tests in the file, all stubbed. All 18 mutants are caught (routing, siblings, positions, the tick, "changed", the focus, the count, the pick, the mirror wording); 161 targeted routing and turn tests pass.

**Third round (the re-check, the foreman's four).**
1. **A real change is never thrown away.** Only a revision whose code is the same, by its parsed tree (comments and layout aside), writes no version. Any other is written. It counts as changed when a PARAMS number, the volume, the bounding box or the centre of mass moved. If none did, it's kept and said with no ✓: "side_left: the code changed, but no number, size or position I measure moved". Pinned: both sides moved 20 mm as literals, a hole moved 100 mm as a literal, and a reshape that keeps volume and centre.
2. **"match" and "the same as" are mirror wording only before a part asked of, "the other" or "each other."** "Make both sides taller to match the top" has no mirror line.
3. **The verb's object wins offline.** With a plural and a named part both present, the request's first clause (before "so", "because", "since" or ";") decides. "Make the legs longer; the top wobbles" is the legs. Joined by "and" there, both are edited. The part right after the verb is its object ("make the top overhang the sides" is the top). When it can't tell, it asks: "Which do you want changed: the legs, or the top?"
4. **Smaller:**
   - rl/rr are positions, "rear" is "back", and "side" is a position, so "the panels" groups side_panel and back_panel.
   - A plural that finds one part only by elimination finds none.
   - A pick on a part the request doesn't change is said: "the pick wasn't used".

53 tests in the file; all 13 of this round's mutants are caught (one survived until the box-only test); 178 targeted routing and turn tests pass.

**Last round (the foreman's two).**
1. **More mirror wording:** "identical", "copy", "the same" (not "the same as", nor "the same thickness as" and the like) and "like the left/right/front/back/other one or side". Pinned: "make both sides identical" and "make both sides like the right one" get no ✓ and the mirror line.
2. **"and" joins two requests, not a request and a complaint.** Only a piece with a change verb or a comparative ("thicker", "2 in longer") is a request. "Make the top thicker and the legs wobble" is the top. "The top is too thin and the legs wobble" asks which.

62 tests in the file; all 7 of the round's mutants are caught; 187 targeted routing and turn tests pass.
