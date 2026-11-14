### 2026-11-14 · CALI-182 (#292) · #293's review: a steep slant is ripped on its face; the PIL pages draw no missing-glyph box

The foreman's round on #293.

- **The slant's words.** "Cut it at 30° from the other face" cut an 11 mm slant where the page draws 33. It now says "plane or router it, or stand it on its face against the fence and rip it with the blade at 30°" (the angle's complement), and "them … their faces" for several. That's on the page and in the book.
- **No box on the PIL pages.** Pillow's default font, which the measure page and the full-size tiles use, has no glyph for "×", the dashes, ½ ¼ ¾, the primes, ✓ ✗ or →, and drew each as a box: the chamfer's and the rebate's two sizes ("6 × 15 mm") were the ones on these pages.
  - **One fix, for every page:** they're drawn by `patterns._page`'s own `ImageDraw` (`text` and `textlength`), which says what the font lacks plainly (`patterns.PLAIN`: "×" → "x", "½" → "1/2", "→" → "->" …). It checks each character against the box the font draws for a glyph it hasn't got, so a font that has "×" keeps it.
  - **What doesn't change:** the cut list, the book, the HTML and the SVG keep "×". Only what Pillow draws changes.

**Tests:** in `tests/test_slants_and_rebates.py`.
- **New:** a chamfered, a rebated and a slanted board are rendered (measure page and tiles), and every string Pillow draws is checked for a missing glyph against its own font. The fallbacks are pinned, and so is a stand-in font that has "×" and keeps it. "×" is still in the text the HTML and SVG read.
- **Reworked:** the slant's words in the three slant cases.
- **Mutants:** 8, all caught. One survived until the stand-in font: treating every character as missing.
- **Around run:** 66 files pass, every pattern-drawing test among them.
