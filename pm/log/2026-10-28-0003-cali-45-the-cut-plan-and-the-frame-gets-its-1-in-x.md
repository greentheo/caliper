### 2026-10-28 · CALI-45 · The cut plan — and the frame gets its 1 in X
- **Theo's calls:** switch to fiberglass; 5/16 shank at 3.3× is fine; fasten the box to the spine too; show
  the cut plan; look at `game-dev/unfold-to-sheets` (his tool: unfold a mesh into flattenable pieces, nest
  onto stock, score lines, DXF/SVG/PDF, seam tokens) — thinking 1 in foam folded at scored lines, spray foam
  and a rasp where it's too curvy.
- **Design:** box v10 BUILD `skin_out` fiberglass (47.5 lb). Frame v16: riser to x −4 in (under the box's
  front wall), spine to the back, shank 5/16 wall, layout *X only, spine to the back* added; `build_spec`
  now splits a wall wherever a frame joint sits under it, so the box is fixed at its front-middle and
  back-middle as well as the corners (6 fixings). Sizing with the shank held at 5/16 (min 3.3×): the walls
  carry the box to the spine and the X only steadies the corners — it drops to **1x1x1/16**. Frame v17:
  shank 13 in 2x2x5/16, riser 8 in 2.5x2.5x⅛, spine 38 in 2x2x⅛, X 4 @ 42 in 1x1x1/16 + gusset = **33.0 lb**,
  **3.57×** (shank), sag 0.31 in; weakest wall 3.6× (glass, wrinkling-limited); front-middle fixing ~110 lbf
  on a bump; the X's middle joint only 234 lb·in now (the gusset can shrink). Design: 130.5 lb with 50 lb
  aboard, **3,147 lb·in standing**. (Spine to the middle, fastened at the front only: 37.3 lb at 3.54×.)
- **unfold-to-sheets integration:** read its SPEC/README — OBJ groups are authored seams and win over its
  curvature segmentation; `resolveStock` takes objects, so Caliper passes 1 in XPS / ⅜ ply / 3/16 plate as
  stock + material objects and needs nothing changed in that repo. `unfold_driver.mjs` (node 22) imports its
  modules, runs `prepare → runScale → buildSheets → buildPackage`, writes the package and prints a JSON
  summary. It scores any fold over 0.5° (a module constant — card); the driver drops folds under the
  material's `score_min_deg` (5° for 1 in XPS) before drawing.
- **First run:** each shoulder was one piece over the doubly curved nose and tail → 5 sheets at 47%, ~330
  score lines per shoulder in a crosshatch (spread 44 mm). **Strip-built instead** (box v11, same shape and
  weight): bands front to back, one per facet of the shoulder curve → 21 pieces on **4 sheets at 59%**, every
  edge exact, 118 score lines (nose and tail; the middle bands are straight). Plywood floor 1 sheet (67%);
  frame: 2 gusset halves on a plate offcut; cut list: 2x2 posts 2 @ 14 in + 2 @ 11.8 in; tubes as above.
- **Rough edges (next):** panels are cut to the outside surface (no bevels or inside-face offsets for 1 in
  foam yet); seam tokens are per facet edge (16 along a band's edge — merging runs between the same two
  pieces would read better; that's on unfold-to-sheets' side); the posts are short now that the shoulders
  lean in — the skeleton wants placing where the shell needs it; tube end cuts (copes at the spine) not yet.
- Tests: `test_cutplan.py` (4; the unfolder ones skip where node/unfold-to-sheets aren't). Full suite green.
- Commit: `8fe590a`
