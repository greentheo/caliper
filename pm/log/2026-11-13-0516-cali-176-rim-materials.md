### 2026-11-13 · CALI-176 (#280) · the rim sees every material; the joint list stays wood (#281 review)

The reviewer found that #281's rim read a finder filtered to wood (plywood, lumber). Two cases lost their rim:
- a 25 mm steel tube on a plywood side: 441 → 63 joint cells;
- a lumber brace on an XPS foam side: 502 → 0 joint cells, so not even the step's edge was kept.

The old `lighten._contacts` probed every piece. No part of Theo's has either case today, but `made_of` sends any sheet part to Lighten.

- **`joints.contacts(..., materials=WOOD)`:** the materials it looks between.
  - The joint list, `fasteners.joints` and the round's joints check keep the default, wood, because glue and screws are about wood.
  - `lighten._met` passes `materials=None`, meaning every piece, so whatever meets a panel keeps its rim.
- **Pinned:** both of the reviewer's cases, on a synthetic stool:
  - the cells under the tube or the brace, and the foam side's top edge under the step, are all rim;
  - the middle stays free to cut;
  - the pair is in the finder's output with every material, but not in the joint list or the shopping list.
- **Measured on scratch copies** of the sample stool and step-stool-5 v3 and v4: rims identical cell for cell to the old `_contacts`, joint lists unchanged (8, 10 and 10).
- **Tests:** 3 new tests, all failing first. One assertion in the new test was wrong at first (it guessed the pair key's order); fixed. 6 mutants on the material set, all caught. The 79 test files around this ran after.
