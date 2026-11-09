### 2026-10-30 · CALI-48 (#4), the rest · Your shop: what makes each piece, and printed parts fitted to the printer
- **Theo:** "let's finish #4 and then step 1 of spec".
- **`shop.py`:** your shop as data, saved once (`~/.caliper/shop.yaml`, or `$CALIPER_SHOP`) and used by every
  design: hand tools from a catalogue (jigsaw, drill, circular saw, hot wire, knife, chop saw, hacksaw,
  welder, angle grinder…) and machines (CNC router with its bed, plasma table with its bed and thickest
  plate, 3D printer with its volume and materials). Nothing saved means a hand-tool shop: jigsaw, drill,
  circular saw. `route()` sends each piece to what makes it: the router if it fits the bed, a jigsaw (up to
  1 1/2 in, curves and holes, with a starter hole), a circular saw (straight, no holes), a hot wire or knife
  for foam, the plasma table within its plate thickness, a chop saw and a welder for tube, the printer for a
  printed part — or says what's missing ("thicker than your plasma table cuts: a fab shop can cut it").
  Foam's fold limit was already enforced: the cut plan makes any fold sharper than `fold_deg` a cut.
- **Printed parts:** a part can declare `{"kind": "printed", "material": "petg"}`; it's weighed from its solid
  (1.2 mm walls + 20% infill) and costed by the kilo (PLA, PETG in the materials table). **`printing.py`**
  fits it to the printer: turned if that's enough, else split across its longest side with three 3 mm pin
  holes, 10 mm deep each side, across every cut (a 400 mm bar on a 256 mm bed: two watertight halves). Time
  and filament come from **PrusaSlicer's command line** where it's installed (0.2 s a piece: 6.6 h, 170 g,
  $3.73 for each half of that bar in PETG), else walls + infill at rough speeds, marked rough.
- **`making.py`:** per part, every piece routed and printed parts fitted and costed. The part panel's *Made in
  your shop* says it in a line per tool ("jigsaw: left side panel, …"), printed parts with hours, grams and
  dollars, and anything your shop can't make in red. A **Shop** page edits the shop. The scorecard checks
  "your shop can make every piece" and reports print hours and filament; the build package files printed
  pieces under `printer/<part>/` and the book gets a *Made in your shop* page.
- Tests run against an empty shop and no slicer (`conftest.py`), whatever this machine has. `test_shop.py`
  (6: the default shop and saving yours; routing for hand tools and for machines, including too-big and
  too-thick; the stool by jigsaw; a printed bar split and pinned, weighed as printed; split pieces fit and
  lose only the pin holes; the scorecard's shop check). `test_scorecard.py` counts the new check.
- Commit: `99ca894` (with CALI-72), PR #37.
