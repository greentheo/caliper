### 2026-11-07 · CALI-118 (#126) · A stray face from the CAD's meshing isn't the part; an open part is said, never thrown
- **The cause:** OCCT's mesher fans a cone face's triangles from its apex, and one comes out with two corners on the
  apex: a sliver of no area along the cone's seam. Any cone that runs to its apex does it
  (`cq.Solid.makeCone(30, 0, 40)`). On Theo's bar stool v7 (a copy) it was face 128, the cone, at its apex on the
  flange (z 14–15.6 mm): 22,772 faces closed and this one apart, so every boolean threw "Not all meshes are volumes!".
- **`measure.clean`**, where every built part becomes a mesh: faces with no area go, and so does a loose open shell
  under `STRAY_SHARE` (1e-6) of the part's surface beside a closed body (it bounds nothing: at the 0.05 mm
  tolerance it moves the volume by about 0.1 mm³ on the bar stool). Said once, `mesh.metadata["strays"]`, and on the
  part card: "I left out 1 stray face from the CAD's meshing (at z 14.0–15.6 mm): it enclosed nothing and weighs
  nothing." A bigger open shell, or a real opening, is kept.
- **An open part is said, never thrown:** `measure.open_near` says where ("near z 40 mm"); `printed_solid` refuses
  a boolean on it, so (on #125's fail-soft) its weight is "not checked: its shape isn't closed near z 40 mm"; the
  strength check (and carve, lighten and the picture, which share `prepare`) says "not checked: its shape isn't
  closed near …, so it can't be voxelized".
- **The bar stool v7 copy:** closed, weighed at 13.1 lb printed included (v7 is a bigger part than v6's 10.9 lb: a
  1 in fillet for ½ in, a new opening pattern; 10.4 L of solid against 7.7 L), scored and released (below).
- `part_scripts.md`: a cone that stops short of its point has no sliver to leave out.
- `tests/test_stray_faces.py` (9; they can't import on main): three real CAD cones, a closed mesh and one stray
  triangle (dropped, said, its weight unchanged), a real opening and a big open shell (kept, said where), a cone
  part weighed whole with the card's line, and an open part (not checked, said, `/balance` 200, the page 200).
  Built on #125 (its fail-soft weighing). Closed is judged as it reads back (merged; #124's
  review). design.js v=65.
