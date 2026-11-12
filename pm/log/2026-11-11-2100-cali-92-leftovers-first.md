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

**Rework from the review (the foreman's six):**
1. **One weight.** The scorecard's `weight.total_lb` is the balance's solid weight plus each part's filament difference, so the card, the scorecard and the book agree. The tongue, the moment and the CG stay on the solid.
2. **A weight or cost goal on a figure that isn't the slicer's is an `estimate`** (no ✓), in `held_to` and the scorecard's check, as `print.*` already is. That covers the rough guess and the solid's share. The rough figure has no supports in it, so an overhanging part reads light. The metrics carry `trust: rough` with the reason.
3. **The panel:** `{build: {}}` is the part as it is, so it gets the figure too. The figure is labelled there, and `mass_kg` is on the same figure as `mass_lb`.
4. **The two stray files** in 835303e (`design.js 0`, `index.html 1`) are deleted. They were copies of `design.js` made by my mutant loop under zsh: `$1` wasn't split, so the restore step `cp m.bak $W/$1` wrote a new file named "design.js 0", and a broad `git add src` took both in. Mutant loops now run in bash from a script file, and I add files by name and check `git status` before every commit.
5. **While the slicer's at it**, a weight or cost goal says "still slicing" (working), not the solid's figure in red.
6. **A bug's `KeyError` is a crash again.** The six API handlers that turned any `KeyError` into a 409 now catch `errors.Refused` (a `KeyError`, so other callers still catch it) and `ValueError`. Construction's and aero's deliberate refusals ("the script has no BUILD dict", "no entry for …") raise `Refused`.

**Rework checks:** 12 new tests (8 for the six items, 4 for `filament_said`); all 9 rework mutants caught. The 41 files around the change pass with no API key (981, without `slow`; a first run of 74 files was cut short and its duplicate stopped). CI has the whole suite.
