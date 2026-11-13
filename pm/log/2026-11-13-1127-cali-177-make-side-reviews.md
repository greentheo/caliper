### 2026-11-13 · CALI-177 (#282) · #283's reviews: a bevel is one plane, a deep chamfer is a chamfer; the kids' book, full-size and projector pages

Both reviews of #283 are folded into one round: caliper-reviewer on the backend, and reviewer-2 on the patterns and the books.

**The backend (caliper-reviewer, accepted by the foreman):**
- **The bug:** a 12 mm chamfer on a 3/4 in edge read as a 45° bevel, and the book said "Set the saw to 45°", which would take the whole edge off.
- **The fix:** a free edge is now read by rays at three depths across the thickness (0.15, 0.5 and 0.85 of it), at three points along it.
  - **Bevel:** all nine rays hit one plane.
  - **Chamfer:** the middle and one face's rays share a slanted plane while the other face's is square. Its size across the edge comes from where the two planes meet. It's said as "chamfer 12 mm (1/2 in), with a router or a block plane: not the saw", on the pattern (a C), the cut list, the book and the kids' book.
  - **Nothing marked:** anything else, such as a small chamfer, a round-over or a taper.
- **Pinned:**
  - **Nothing marked:** square, a 3 mm chamfer, a 10 mm round-over and a tapered outline.
  - **The 12 mm chamfer:** reads as a chamfer, with no "Set the saw".
  - **A true 20° bevel:** still reads 20°.
- **Theo's scratch copies are unchanged:** step-stool-3 v2 still reads 10° on its 6 edges, and step-stool-5 v3 has no bevels.

**The patterns and books (reviewer-2's five must-fixes):**
1. **The kids' book's tenon:** it read "push the right side through the stringer". It now says which piece goes through which: "Put glue in the hole in the left side, then push the stringer through it", and, where the side goes on last, "Put glue in the hole in the right side, then slide it onto the end of the stringer".
2. **The kids' book's cut step** now cuts the slots: "For the slot in the left side and the right side (the grey box on each pattern), the grown-up drills a hole just inside the line first".
3. **It tilts the saw for the bevels:** "Some edges are marked B on the patterns: for those, the grown-up tilts the saw to 10°, printed side up". It also has a line for chamfers.
4. **The full-size pages, cover and measure page** now cover the dashed lines and cuts (`patterns._extent`). On the splayed side's foot, the line 1/8 in past the outline used to fall in the printer's margin; it now prints.
5. **The words where you cut from:**
   - the projector SVG has B, C, M1, N1 and D1 labels, and every mark's sentence;
   - the full-size cover (`map_lines`) gives every mark's sentence, and draws the marks.

**reviewer-2's small asks:**
1. **Axis numbers:** the measure page's numbers sit clear of a dashed line past the outline.
2. **B label:** placed inside by its dashed line's distance plus a margin.
3. **Extra wood:** "Leave 1/8 in past the solid line along the 1 edge whose dashed line is outside it: … cut the blank big enough first".
4. **Kids' book drill list:** "a 3/16 in drill bit and a countersink, for the holes at each + on the patterns", beside the pilot bit.
5. **Joints table:** an assumed through tenon or notch is listed as "glue", not "glue and screws", as the steps say.
6. **Shopping line:** "1 1/2 in from each end of a joint, then no more than 6 in apart (at each + on the patterns)".
7. **Page text:** the measure page's and cover's words are 14 px (about 6.7 pt printed), up from 12. M1 sits beside its box.

**Tests:** 9 new for reviewer-2's items, all failing first, plus 6 for the chamfer review, which fail on the reviewed commit (the 12 mm case as a bevel, and the others on the missing chamfer list).
- **Two tests changed, both wrong rather than the code:**
  - `test_joints::test_every_contact_without_an_entry_is_listed_as_an_assumed_butt` pinned "glue and screws" for an assumed through tenon, which small ask 5 replaces.
  - My own first full-size tile test found the dashed line as the "outline" once it printed. It now finds the solid line by its unbroken run.
- **Mutants:** 20 on this round, all caught: 7 on the chamfer reading, and 13 on the kids' book, the tiles' extent, the SVG labels and words, the cover, the extra wood, the joints table and the shopping line.
- **Around run:** the 44 test files around these changes pass.
