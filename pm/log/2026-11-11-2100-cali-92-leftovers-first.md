### 2026-11-11 · CALI-92 (#70) · The leftovers, first part: the heading, a stale cut, the kids' book view, one filament number

Four of the items main still had after the triage of 2026-11-10.

- **21. The part view's heading** is the part's own name. Its id and how it was made (`parametric`, `imported`, `whittled mesh`) sit in the Advanced line, one click down.
- **24. A stale run doesn't offer the cut.** A Lighten or carve of an older version doesn't offer "Cut these holes" or "Carve it like this" in its preview bar, since the server would refuse it (CALI-87). The bar says "This lightening is of v3, and the part has changed since (it's v4): lighten it again." Any 409 is now a plain line with no **Report it…**: it's a refusal the server meant, not a bug.
- **14. Each step of the kids' book looks at the panel it adds.** The book drew every step from one view: toward the pictured side, or else 35°, which looks from the back. So "Add the front" drew the front behind the rest. A wall the book's view has its back to now gets a view that looks at it, toward the front where it can. A wall the view already sees keeps the book's own view.
- **23. One filament number** (the foreman chose option (a)). The card said 1122 g (the model's solid) and the shop panel 726 g for one print. Each printed group's filament is now the making plan's figure: the slicer's, or its rough walls-and-infill guess where there's no slicer. Where the plan has neither, it's the model's solid share. Each figure says which it is. The part's weight goes with it. One `making.filament` feeds the buy card, the design's weight and cost totals, the scorecard's weight, cost and shop check (planned once, while weighing), the book's shopping list, and the Built-from panel. The book's note "The shopping list goes by the model's weight… can differ a little" (#182) now says the figures are one; #182's test is updated to match.

**What moves (item 23).** Measured on the mixed stool from the walk (`test_mixed.MIXED`, no slicer):

| | before | after |
|---|---|---|
| filament | 1122 g (no label) | 726 g, "a rough guess", the shop panel's figure |
| weight | 3.5 lb | 2.6 lb |
| What do I buy? cost | $70.69 | $61.97 |

The step-stool and camper samples have no printed part, so nothing of theirs moves. The strength study's own weight (self-weight in a case) and the centre of gravity still use the model's solid: item 23 is about what's said and bought.

**Tests:** 17 in `test_leftovers_70.py`, one (two cases) in `test_kidbook.py`, and #182's two. Every one fails on main. 16 mutants are all caught: 4 on the stale bar and the 409, 4 on the kids' book view, and 8 on item 23, one per place that reads the figure.
