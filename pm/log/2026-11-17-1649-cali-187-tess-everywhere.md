### 2026-11-17 · CALI-187 (#298) · slice 2: every mesh the app reads, read straight off OCC

The foreman's next slice after #340: move `measure._cadquery_to_trimesh`, `pieces._meshed` and `features.py` onto
`caliper.tess.triangles`, from fresh main (fdad181).

**Now:**
- **`measure._cadquery_to_trimesh`** (every build, so every check) reads `triangles(solid, tol, 0.1)`, `tessellate(tol)`'s
  own angle. It's cleaned as before.
- **`pieces._meshed`** reads `triangles(shape, 0.05, 0.1)`.
- **`features.of_solid`** reads each face with `triangles(f, LINEAR, ANGULAR)`. A face's only face is itself, and CadQuery's
  `Face` doesn't override `tessellate`, so it's the face's own `tessellate()`. The hollow test takes the first point as an
  array now, where it took a Vector. My code was wrong there on the way: a cylinder's face threw `toTuple`.
- Nothing in src calls `.tessellate(` now, and a guard says so.

**The same numbers, on Theo's designs.** Scratch copies of `i-want` (the bar stool) and `step-stool-5`, their parts and
YAML only, were run through main (fdad181) and through this branch, each on its own copy. Each run covered every part's
mesh (a hash of vertices and faces), its page features (a hash), its declared checks, a fresh strength check, and the
scorecard. **All identical**: the bar stool's strength check reads 0.34 both ways, step-stool-5's 2.15, with every case.
The copies are deleted.

**Time** (the same runs; a full suite was running beside them, so roughly):

| | main | this branch |
|---|---|---|
| bar stool: build and mesh | 7.75 s | 5.97 s |
| bar stool: page features | 10.05 s | 8.26 s |
| step-stool-5: build and mesh | 4.02 s | 2.54 s |
| step-stool-5: page features | 8.98 s | 7.27 s |

The mesh alone at 0.05 was 0.789 → 0.170 s on the bar stool (#340's table). The rest is the build and the features' own
work.

**Tests** (tests/test_tess_everywhere.py, 19). Each is pinned against CadQuery's `tessellate()`, called in the test with
the arguments main used:
- every build's mesh, on #340's five fixtures, at 0.05;
- a Workplane's first solid;
- a pieces difference;
- the page's faces, and placed by a pose;
- a hole's wall reads hollow and a post's doesn't.

Those pass at main too: they're the same-numbers pins. The four that failed at fdad181, run from a scratch tree:
measure, pieces and features never calling `tessellate()`, and the guard.

**What my tests were wrong about on the way:**
- **The identity pins compared the code with itself.** They swapped `tess.triangles` for a `tessellate()`-backed one and
  ran the same function, so a wrong argument went to both sides: 6 of 9 mutants survived. They're against
  `tessellate()` with main's own arguments now.
- **No fixture had a hollow cylinder,** so the hollow test's point was unchecked. A plate with a drilled hole and a post
  pins it.
- **The guard caught tess.py's own docstring.** It skips tess.py.

**Mutants (9), all caught on the second pass,** each run against test_tess_everywhere.py:
1. measure's angle not tessellate's
2. measure's tolerance not the caller's
3. measure back on tessellate
4. pieces' angle not tessellate's
5. pieces back on tessellate
6. the face's angle dropped
7. features back on tessellate
8. the pose ignored
9. hollow read from the face's centre
