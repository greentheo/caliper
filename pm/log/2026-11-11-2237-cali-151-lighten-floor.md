### 2026-11-11 · CALI-151 (#207) · A Lighten that saves a few ounces doesn't get a button

From the reviewer's re-check of #201. A Lighten is exempt from the $1 floor, since the sheet is bought whole. But every
hole is a cut in the shop plus a re-check, so a few ounces is the same waste as a 7¢ carve, paid in labour.

- **The floor:** `use_step.LIGHTEN_MIN` is a quarter pound or 5% of the part, whichever is larger. It's a judgment call,
  like `USE_MIN_USD`. A Lightening records the part's weight (`part_lb`, from construction). An older one that
  doesn't record it goes by the quarter pound alone.
- **Under it there's no Use it.** The card reads "No step of the lightening to use: it would make it 0.4 lb lighter, at
  almost no cost in strength: too little to be worth the cuts and a re-check, so it's left in the study". The panel
  calls that step "Its best step", not "The step to use". The steps stay in the study to choose by hand.
- **"That step is there to choose"** is said only of a deeper step the re-check can see. Of one it can't, it says "The
  study got as far as …, but the re-check can't see that step's walls, so it couldn't be settled".
- **The Studies line for a carve with nothing to use** ("nothing to use, and why") is pinned. Its mutant survived on
  #201.

It doesn't bite on anything stored: the box stool's offer is 3.35 lb, and its smallest step is 0.74 lb (the reviewer's
figures).

**Tests:**
- 12 cases in `test_lighten_floor.py` (8 tests, one over 5 weights);
- `test_lighten`'s real run pins the recorded weight;
- all 10 mutants are caught;
- the around-files (7) pass, 177.

**Rework from the review (the foreman's three).**
1. **The floor decides only whether there's a button.** It tested the step `choose` picked, so with a 0.1 lb (no room)
   or 0.2 lb (room) pick, the card said "too little" while a 1 lb step that's seen and holds sat in the study. Now
   under the floor it still says "The study got as far as 1 lb lighter, and that step is there to choose" where a
   deeper seen step is over the floor.
   - The card leads "The lightening's step isn't offered", and the panel says "Too little to use", never "best".
   - Both of the reviewer's cases are pinned.
2. **The floor is `min(1 lb, max(0.25 lb, 5% of the part))`**, in `LIGHTEN_MIN` with the reason: it's labour, not
   safety, and a pound saved is a pound carried. The foreman's call for now; Theo can move it.
3. **An older run of the current version** takes the part's weight from its construction now. The quarter pound is
   only where that can't be read. A run of an older version doesn't take today's weight.

16 tests in the file; 8 more mutants, all caught. The quick around-files pass (172).
