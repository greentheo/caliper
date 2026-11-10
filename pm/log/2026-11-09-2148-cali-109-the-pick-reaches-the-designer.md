### 2026-11-09 · CALI-109 (#109, slices b and c) · The designer uses the pick, and the round checks it landed
Theo, after the bar stool's fillet went on the wrong edge: "perhaps in the UI i could select an edge or a face to further
clarify what I'm talking about?"
- **The guide says how** (`part_scripts.md`): `NearestToPointSelector` at the point the message gives, at the step where that
  edge or face exists, and never a `">Z"`-style selector.
- **The round checks it landed** (`features.landed`): a fillet on an edge (the edge gone, a round of about that radius
  there, a torus on a circle) and a hole through a flat face. It compares the part's faces and edges before and after.
- **A miss comes first and the turn isn't a success:** "✗ The edge you picked is still there, so the fillet didn't land on
  it." No tick above it. A round of the wrong size is a miss too, and says both numbers.
- What can't be measured says so, and neither fails the turn nor claims a hit.
- The page sends the pick with the message (`pick: {kind, id}`).
- No live designer run: "fillet this 1/2 in" on the stool waits for #155 and Theo's word.
- Tests: tests/test_features.py (62, the designer stubbed). Seven mutants each fail.
