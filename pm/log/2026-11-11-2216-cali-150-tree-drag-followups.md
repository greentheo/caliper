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
