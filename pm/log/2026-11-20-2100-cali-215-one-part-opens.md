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
