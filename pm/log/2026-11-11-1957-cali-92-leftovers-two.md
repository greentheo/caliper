### 2026-11-11 · CALI-92 (#70) · The leftovers, second part

The rest of #70 after #237: the reviewer's three weight notes, #235's three, #209's four, the `filled()` follow-up,
reviewer-2's router cases, item 10 and item 20. Stubbed models only, no live calls.

**#237's weight notes.**
- The solid's share of filament is an upper bound for the model as drawn (`making.filament_bound`), as the reviewer put
  it. A slicer may add supports, so it's a bound on the part, not on what a printer lays down. Under a weight or cost
  limit on it, a goal passes. Over the limit, it may still be under, so it's an estimate, not a ✗.
- The panel says so under the materials table: "The table below, the pieces' weights and the balance are the model's solid
  (X lb); its weight above, Y lb, goes by its filament figure."
- **Only the printed share is the bound: the wood weighs what it weighs.** The around-files caught this:
  `test_printed_release`'s 0.2 lb goal on the mixed stool read "estimate", though the plywood top alone is over a pound.
  Now a weight goal is settled where the total with the printed share at nothing gives the same answer
  (`making.solid_share_lb`). A limit under the wood alone is a ✗ on the card and the scorecard. That was the code's
  fault, not the test's.
- A part's weight row says "rough" and the source of its figure.
- On main, a piece the slicer failed on crashed the print-hours sum. Now it reads "can't be worked out: the slicer couldn't
  for the …".

**#235's three.**
- **Under 0.1.** A very slender wall reads "under 0.1 times over", not "only 0 times over". The card, Studies and the
  page say it alike (`safety_num` and `safetyNum`), and a fail line drops its "only".
- **A slant.** Slants of 8° and 20° leave one pair of edges reading as along the load but the other not square. They're
  now pinned as "the load runs at a slant", so the reviewer's mutant that drops the "every edge near square or along"
  clause is caught. For a rectangle that clause is what holds the slant to about 5.7°; SQUARE is unchanged.
- **A shove in a sheet's plane** is taken as squeezing it end to end, the safe side (the test stool's top, 20.9×).
  No verdict moves (Rule 6: numbers first). Each buckling row now says whether its load runs down the sheet (`down`).
  Where it doesn't, the card and the page say: "The top folds first, taken as squeezed end to end by a push that
  doesn't run down it: the safe side, as a shove more likely racks it than folds it". Whether to check racking
  instead is Theo's call.

**#209's four.**
- `promise()` skips lumps (a hinge, glue, screws). It reads a stick with no material as lumber, as
  `construction.piece()` does. A plywood part with a hinge keeps the wood words.
- A ring seat's trial basis says "on a ring beneath it", the ring check's own words.
- The build book's promise keeps the card's "Printed parts are a rough model…" where a released verdict rests on the
  printed model.
- Every reader names both causes: "a solid with more in it than its pieces". That covers the scorecard, Studies, the
  run's note ("its shape filled in, or a piece missing from its construction"), the book's cell, the chat's facts, and
  the page's Lighten and carve lines.

**`filled()`.** The design card's goal and the scorecard take the current run's own `filled` as filled, as the card's
verdicts already did. A run of this version that ran on such a solid is never a ✓ there because `filled()`, asked
now, can't tell.

**reviewer-2's router cases** (`chat.offline_classify`):
- A plain-words question is an answer, on an empty design or a stool. That holds where its direction word follows
  "and" in a question ("why is it wider and heavier"), follows a dash, or is in a statement ("it's heavier than I
  thought").
- "I need them painted" with the part selected is a change. "I need it by Friday" and "I need it" aren't.
- A change after a colon, a dash, "so", or "can/could you" is the change: "I don't get it - make it 2 inches taller".
- On an empty design, an explain-plus-change has nothing to change, so no part is named `i_don` or `explain_why`.
  "add a step stool" still authors one.
- `named_part` knows the tree's labels, so "add the missing piece to the Bathroom stool" reaches the renamed part
  with nothing selected.
- One assert on the part card's text pins `pid` at `part()`'s `fix_for`.

**Item 10, a carved part released.** Run on a mixed stool carved with a window out of each printed side, with a printer
in a scratch shop.
- The print files come out as the carved shape. Their volume is the two sides less their windows, within 2%.
- The build book points at them.
- The patterns and the cut list are the plywood top's.
- **Found:** `source/stool-v002.py` named `carved-x-01.stl`, which wasn't in the package, so the released source
  couldn't build. The mesh is now kept at `source/carved/`, and the source builds from the package alone.
- The kids' book is only made for all-wood builds, so there's none here.

**Item 20, a 1024 px window.**
- Between 701 and 1279 px, the chat keeps its column (320 px) and the cards drop under the view, which takes the width.
  Collapsing the chat would hide the conversation, which is the app. No hosted spec is in the repo or the issues, so
  this choice is the foreman's to overrule.
- Fit now stands back by 1/aspect in a view narrower than it is tall. Views as wide as they are tall or wider are
  unchanged.
- Checked in a browser on :8016 with scratch designs:
  - At 1024 px the view is 704 × 430 (was about 220 wide) and fit frames the stool.
  - At 800 px it's 480 wide with no sideways scroll.
  - At 1440 the three columns are as before.
  - On a phone's view pane, fit frames the whole stool across.
  - Studies sits beside the chat.
  - No console errors.

**Checks.**
- 43 tests in `test_leftovers_70b.py`. All 28 mutants are caught. One survivor at first (the page's shove words)
  now has a page test.
- `test_filled_verdict`'s expectations moved to the both-causes words.
- The 27 around-files: 728 pass, with 1 failure, the 0.2 lb goal above (fixed in the code).

**reviewer-2's two small asks on item 20.**
1. **A resize re-frames until the camera is moved.** A live resize past square (1024 to 701 px, or a phone turned)
   left the stool framed for the old shape, cut off at the edge. Now, while the camera is where fit put it, a resize
   runs fit again. Once the person orbits, pans or zooms (the controls' `start`), a resize leaves it alone.
   Checked live in a browser, 1024 to 701 px with no fit pressed: the whole stool stays framed. 4 mutants, all
   caught.
2. **Item 20 pinned.** That's already in this PR's `test_leftovers_70b.py`: `narrowBy(0.5) == 2` and the 701–1279 px
   rule (cards under the view, the chat down both rows).
