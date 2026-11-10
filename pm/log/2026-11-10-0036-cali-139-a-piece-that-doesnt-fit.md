### 2026-11-10 · CALI-139 (#179) · A piece that doesn't fit the printer is never ok
Found walking the stool: the card, `/making` and the scorecard all said every piece could be made, and "measured", with three
pieces each wider than a 256 mm bed. The split cuts across the longest axis only, and nothing checked the result.
- `printing.too_big` checks every piece. Any that don't fit: `ok` is false, the piece is in `missing`, and nothing is sliced.
  The card says "cut into 3 pieces, all 3 are too big: the biggest is ..., and your printer takes ..., less 5 mm clearance: section
  it differently, in the chat, or use a bigger printer".
- The scorecard's "your shop can make every piece" reads the same answer.
- From the review: a printed piece the shop can't make leaves no print total for the design, as a failed slice does. A time goal says
  why, on the card and on the scorecard, and can't pass on the other parts' hours. The design's own card names the part that doesn't fit.
- A refusal, not a cleverer split: how to section a 23 in cone is a design call.
- Tests: tests/test_print_fits.py.
