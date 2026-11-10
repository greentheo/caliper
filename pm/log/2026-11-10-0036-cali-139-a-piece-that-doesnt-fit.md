### 2026-11-10 · CALI-139 (#179) · A piece that doesn't fit the printer is never ok
Found walking the stool: the card, `/making` and the scorecard all said every piece could be made, and "measured", with three
pieces each wider than a 256 mm bed. The split cuts across the longest axis only, and nothing checked the result.
- `printing.too_big` checks every piece. Any that don't fit: `ok` is false, the piece is in `missing`, and nothing is sliced.
  The card says "cut into 3 pieces, one is still 583 x 583 x 246 mm, and your printer takes 256 x 256 x 256 mm".
- The scorecard's "your shop can make every piece" reads the same answer, and there's no print time for pieces that don't fit.
- A refusal, not a cleverer split: how to section a 23 in cone is a design call.
- Tests: tests/test_print_fits.py.
