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
- Tests: tests/test_features.py (124, the designer stubbed). Seven mutants each fail.
- **#177 review, redesigned:** three outcomes, and the default is "I couldn't tell whether that landed". Landed needs the picked edge gone and a new round between that edge's own two faces, where it was; missed needs the same edge still there, on the same two faces. A chamfer, a neighbour's fillet or an unrecognised surface can't read as either. Holes likewise (a new through-hole in the picked face; not a boss, a corner fillet or a blind hole).
- **`edge_at`** is in every script's namespace and measures true distance to an edge, because `NearestToPointSelector` measures to the centre and concentric rings tie. On a copy of the stool all 563 edges return themselves.
- **A miss doesn't block trying again:** no "already did that", and a parked repeat keeps its pick so "yes" runs the same check.
- **#177, last round:** a straight pick takes only a cylinder along it, and a curved pick never a cylinder, so a neighbour's round can't read as landed on a short edge. A hole's face is the picked face, not its plane, and a post isn't a hole. A round on the right edge at the wrong size reads "!" at the top, gives both numbers, and isn't a success; trying again is the next step.
