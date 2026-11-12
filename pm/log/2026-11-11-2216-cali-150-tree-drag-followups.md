### 2026-11-11 · CALI-150 (#206) · Part tree dragging: the waiting line, the last row, and pins

reviewer-2's follow-ups from #204. None touches data, apart from the one below.

1. **The waiting line belongs to its design.**
   - It was in the tree's header, which scrolled away. The header is sticky now, so it stays at the top of the tree.
   - It followed to another design for about 32 s, saying "this design". Now a switch clears it (`seen()`), and the
     600 ms timer shows it only on the design the part was moved in.
   - **Found on the way:** a move that came back after a switch wrote the old design's reply into `S.design`. The
     other design's tree and parts would then have shown the first one's. Now a reply that comes back to a design
     no longer open is left there (it was saved), with no redraw and no error shown here.
2. **The "after" line under a chosen last row.** It was an inset shadow on the part's block, and the chosen row's own
   background painted over it. It's now a 2 px line drawn over the block's rows (`.tpart.drop-after::after`).
3. **The wiring is pinned:**
   - `renderTree` itself runs, with stubs: it drags on a desktop and not on a phone, and says what it's waiting for.
   - The phone query is the CSS's phone breakpoint, and turning the phone redraws the tree.
   - The CSS has the sticky header and the line over the rows.

**Checked in a browser** on :8016 with scratch designs:
- with the tree scrolled 100 px, the "Parts" header stays at its top;
- with the last piece ("top tread") chosen, the after line shows under it.

The console's only errors were connection-refused, from the tab polling :8016 while no server was up between two
previews.

**Tests:** 8 new in `test_tree_moves.py`, plus one assert on the drop test (the reply becomes the design shown).
Five of the new tests fail on main. The other three pin wiring that works today. All 12 mutants are caught; one
survivor at first (`S.design = got`) now has its assert. `test_tree_moves` and `test_part_tree` pass (93).

**Rework from reviewer-2's review (the foreman's three).**
1. **A switch draws the tree at once.** `showLoading` clears the waiting line and draws the tree as "Loading <name>…" with
   no rows, so nothing of the old design is left to drag. Before, it only hid the tree, with the old rows still in it.
   With no design loaded (`S.design` null), nothing in the tree moves:
   - a drag doesn't start;
   - a dragover or a drop isn't taken;
   - `moveInTree` returns.

   The `null`-`tree` TypeError can't come up. Checked in a browser: switching to the stool with its load slowed, the
   tree read "Parts · Loading Step stool…" with no rows, then the stool's own tree came. No errors.
2. **A move that fails while you're away is said when you're back:** "Your move of c in x didn't save: …", once
   (`TREE.missed`, `sayMissed` after the design opens).
3. **Back on a design whose move is still waiting, its waiting line comes back.** `TREE.waiting` holds each design
   whose move has waited past 600 ms, until its reply.

**Tests:** 7 more in `test_tree_moves.py`. `test_part_tree`'s copy of the TREE line now matches the page's. All 13
mutants are caught (two survivors at first now have tests). The two tree files pass (100).

**CI at 8eabdd1: 7 design-switch tests failed.**
- **Five were stubs missing the rework's new collaborators.** `test_design_switch`'s and `test_pick_scope`'s stub pages
  had no `sayMissed`, now called by `openDesign`, and no `TREE`, now used by `showLoading`. They get the stubs; no
  expectation moved.
- **One test pinned the old draw order:** `test_design_switch::test_the_new_design_s_name_goes_up_at_once…` asserts
  the tree is hidden while a design loads. reviewer-2 since found the old code already hid it from the switch to the
  load, so A's rows were never on screen, and the TypeError came from a synthetic drop on hidden rows.
- So, as the foreman asked, only the harmless part of the rework is kept. `showLoading` hides the tree as before, and
  now also empties its rows and clears the waiting line. The "Loading <name>…" tree is dropped, and the test's hidden
  assertion stands with two more: no rows, no waiting line.
- The `S.design` drag guards, the lost-move line and the returning waiting line stay.

151 pass across the switch, pick, tree-move and part-tree files; 3 more mutants, all caught.
