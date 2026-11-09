### 2026-10-28 · CALI-52 (part 2) · Three beams, a glass patch, and the skeleton on screen
- **Theo:** the local patch — yes; jacks under the corners of the X; three beams (2.7×); "let me know when I
  can see the skeleton (maybe we can toggle off each object/layer?)".
- **Box v14:** `roof_beams` 3; `corner_patch: glass_patch` — a new covering (one more layer of 6 oz + epoxy,
  no paint, 0.41 kg/m²) as a stand-alone `covering` item over the front panel's corners (4 in past where
  the shoulder starts, up to the corner beam's depth), and the front corner wall beams carry it as one more
  skin. Walls 3.37× → **4.98×**; +0.5 lb (½ yd of cloth). Scorecard **8/8**: 141 lb on the hitch, snow 2.7×.
- **As-built view:** `pieces3d()` + `/pieces` route; the page draws sheets (translucent, edged), sticks and
  tubes (boxes on centrelines), plates (ExtrudeGeometry on their placement basis, both cheeks); a layers
  panel toggles floor / panels / shell / patches / skeleton / tubes / gussets and a faint solid; parts
  re-fetch when their version changes. Checked in a background tab: the 1x2 frames, three beams and patches
  on the box; the X, spine, riser and the brass cheek plates on the frame.
- **Next:** the parked case on jacks under the X's back corners, with Theo inside (< 350 lb total) — the
  floor over the X under a person, the jacks' loads.
- Tests: `test_construction.py` +2. Full suite green.
- Commit: `568880b`
