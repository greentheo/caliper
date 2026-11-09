### 2026-11-09 · CALI-109 (#109, slices a and part of b) · Pick a face or an edge, and the chat knows exactly which
Theo, after the bar stool's fillet went on the wrong edge: "perhaps in the UI i could select an edge or a face to further
clarify what I'm talking about?"
- **Each face and edge has an id** (`caliper.features`, `…/parts/{pid}/features.json`): a face tessellated as its own group,
  an edge as a polyline, each with its type, centre, axis and radius, and for an edge its two faces and whether it's an
  inside or outside corner. In design coordinates, with the script's own centre beside it. Worked out once per version and
  kept beside the part. On a copy of the stool: 193 faces, 563 edges, 1 MB, and the inside circle at the foot is there.
- **Part, Face, Edge** in the view bar (the mockup's). A click says which, highlighted in amber, and the chip reads
  "edge: the circle where the flat face meets the cone, 18 in across, 0.6 in up (inside corner)", in the person's units.
- Edge picks go by the nearest edge on screen, not through the part, and a click just off the silhouette still finds it.
- A part with no B-rep (carved, whittled, imported) gives a point with its coordinates.
- **The message carries the pick:** "About this edge: … (at x, y, z mm in the script's coordinates): fillet this".
- Not yet: `NearestToPointSelector` guidance in part_scripts.md, and the check that the change landed on the pick (slice c).
  No live designer run has used a pick: live runs wait for Theo's word after #155.
- Tests: tests/test_features.py (33). Mutants each fail (triangle lookup, edges through the part, no pixel limit, a corner
  flipped, no pose, a cache that ignores placing).
