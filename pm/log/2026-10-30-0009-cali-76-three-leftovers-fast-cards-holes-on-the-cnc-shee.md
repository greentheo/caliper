### 2026-10-30 · CALI-76 (#44), CALI-77 (#45), CALI-68 (#28) · Three leftovers: fast cards, holes on the CNC sheet, measuring error
- **Theo:** "Please do the seven PR merge stack. Then Showcase 1 and the three leftovers." The stack (#25, #30, #33,
  #35, #36, #37, #41) is merged into `main` in order, each retargeted to `main` and merged with a merge commit;
  nine issues closed with it (#1 stays open: #30 was one slice). #8 went up as PR #43 into `main`.
- **Cards in under a second (#44):** one set of four cards ran `construction.declared()` nine times, each the part's
  script in its own process (~1.5 s), always on the same script: 13.4 s of 13.4 s on the stool. Now cached by the
  script's text and BUILD what-if (a change to the script is a new key; callers get a fresh copy): 0.9 s.
  `design_state` on a warm server is 6 ms.
- **Holes on the CNC sheet (#45):** a holed panel goes to unfold-to-sheets as triangles round its holes
  (`cutplan.holed_face`: manifold3d triangulates it in the outline's plane, wound as the outline faces), so the
  unfolder reads them as the piece's inner boundaries and cuts them. The note now says to cut the holes before the
  outlines. **A bug it found in unfold-to-sheets:** a piece was lined up by the principal axes of all its points,
  so an off-centre hole tilted it on the sheet (0.13° for a 2 in hole; a rounded window, more).
  greentheo/unfold-to-sheets#2 lines a piece with holes up by its outline (one without holes as before; 145 tests
  pass); `UNFOLD_REF` is pinned at its commit `8fc66c9`. Theo's own checkout (`vendor/` links to it) needs that PR
  merged and pulled before the new cut plan test passes locally.
- **Measuring error (#28):** a drafted rule on `min_wall` or a `bbox` size has the measurement's tolerance written
  into it (`promote.MEASURING`: a wall 0.15 mm, a size 0.1 mm, from the 0.05 mm tessellation and the ray-cast):
  `min_wall >= 19.05 - 0.15` holds for 3/4 in ply measured at 18.98 and still fails 5/8 in. An `==` on a size
  becomes a band. The offer says what the allowance is; `_bounds` folds the arithmetic, so contradictions are
  still caught.
- **Filed for Showcase 1 (#10):** CALI-78 (#46) a picture on it (the T-rex, cut out and still holding Dad),
  CALI-79 (#47) a build book a kid can follow, CALI-80 (#48) record the test, predicted against measured. Knock-down
  joinery stays with #9. Next free id: CALI-81.
- Tests: `test_answers.py` (the declarations are read once until the script changes), `test_cutplan.py` (a holed
  panel's triangles: the panel less the hole, facing out, eight boundary edges; the stool's left wall with a 2 in
  hole cut on its sheet), `test_promote.py` (18.98 holds a 3/4 in wall rule, 15.88 doesn't; only measured sizes
  get the allowance; a drafted rule says so), the old exact-text expectations updated. **Full suite: 515 passed**
  (with unfold-to-sheets at `8fc66c9`).
- Commits: `916745e` (#44), `f3ccee0` (the pin), `2db111e` (#45), `7622e00` (#28). PR #49.
