### 2026-11-20 · CALI-215 (#362) · a one-part design opens on its part, so "Check it holds" is there at first look

From Theo's live test on step-stool-5. The page opened on the design view, which has the part's Parameters but no action
bar, and he couldn't find *Check it holds*. The bar (`partActions`, #325) is only in the part view.

- **`soleFor(design)`:** the part's id when the design has exactly one part and it isn't a reference; otherwise null.
- **`openDesign`** sets the scope to it before the first draw. The page opens in the part view, with its bar, its cards
  and the chat chip. The design view is the chip's × away. A refresh never re-scopes, so × sticks until the design is
  opened again.
- **Not done this way:** the bar copied into the design view. Its buttons are wired by `wireInspector(p)` to the part
  view's own panels (`loadBox`, the progress lines, job tracking), so they'd run with nowhere to show.

**Walked on 8021** (a fresh scratch copy of step-stool-5): the first open shows the part, with *Check it again · Lighten
it again · Make the cut plan again* and "talking about Step stool". × gives the design view. The camper (three parts)
still opens on the design.

**Tests:** `tests/test_one_part_opens.py`, 7 tests: one part, two, a lone reference and none; step-stool-5's open, scoped
before its first draw; a two-part design unscoped; the bar being the part view's. Six fail on main. Five older Node
harnesses that extract `openDesign` (test_design_switch, test_pick_scope) now extract `soleFor` too.

**Mutants, 5 of 5 caught:** any part count opens on the first; a lone reference opened on; no scope set; the scope set
after the first draw; an empty design scoped.

**Round 2 (reviewer-3 on #364): shown, not scoped.** Opening scoped changed the chat: a scoped message is that part's
revise, so on step-stool-5 "add a matching bench" (and 13 of 17 such phrasings) rewrote the stool instead of making a new
part. Now:
- **The panel shows the part, the chat isn't scoped.** `shownPart()` is the part whose view the panel shows: the one
  picked, else a one-part design's own part, unless the person asked for the whole design (`S.whole`). `S.scope` stays
  null on open, so the chip, the tree's selection and what a message is about are exactly main's.
- **Every panel that asked "is my part on screen?" by `S.scope` asks `shownPart()`:** renderInspector, the cards'
  answers and their key, Things to fix, the Fix these button, Built from, Made in your shop, the carve's progress, a
  job's panel line, and whittle's redraw. Otherwise the part's view, drawn unscoped, would never paint its own progress.
- **Both views lead to each other.** "The whole design ▸" under the part's name gives the design's view, and "◂ Step
  stool: check it, fix it, make it" gives the part's back.
- **`openDesign` resets `S.piece` and `S.focus`** with the scope. step-stool-4's picked "left side" had come over as
  "Step stool · left side".
- **test_tree_moves' pin of `openDesign`** (`S.design = got; doneLoading(); render(); sayMissed();`) holds again, with
  the resets moved to its first lines.

**Walked on 8021:**
- On step-stool-4, I picked Step stool · left side, then switched to step-stool-5. It shows Step stool's view with the
  bar (Check it again · Lighten it again · Make the cut plan again). There's no chip and no lit piece, and the placeholder
  reads "Click a part to talk about it, or ask about the whole design…".
- "add a matching bench" was posted with `"scope": null`.
- The whole design ▸ and back both work.
- Check it again from the unscoped view painted "voxelizing 'step_stool'…" in its own panel.

**Mutants** (`$S/mut/mut364.py`, on test_one_part_opens), 16 of 16 caught:
- **soleFor:** any count; reference shown.
- **shownPart:** whole ignored; scope ignored.
- **openDesign:** scoped on open (the old way); piece comes over; whole kept.
- **A panel judged by `S.scope` again:** panel by scope; carve by scope; jobs by scope; answers by scope; fixes by
  scope; fix bar by scope.
- **The links:** no way to the design; no way back; links unwired.

**Round 3 (reviewer-3's re-check): the rest of the part view's readers.**
- **History's Preview and Go back** did nothing in the unscoped part view: their click handler read `S.scope`. They read
  `shownPart()`.
- **Swept** every `S.scope` read that's about which part's view is on screen:
  - `focusCard` (the card's 3D view);
  - `cardStore` (which card is kept open);
  - `cardsView`'s focus and "show this in 3D";
  - `showMarks` (the part's weight, CoG and keeps in 3D);
  - `reportError`'s "a part's cards";
  - `goTo`'s way to the build package, which now asks for the whole design's view.
- **What stays on `S.scope`:** the chat, the chip, the tree's selection, picking and the keyboard's menu.
- **The test harnesses:** `test_carve_click._page` and `test_small_words._js` bring the page's own `soleFor` and
  `shownPart` along whenever an extracted function calls `shownPart()`. test_fix_act's three failures were this.
- **Walked:** step-stool-5's unscoped part view → History → Preview v13 shows its bar, with Go back. The chip stays
  hidden.
