### 2026-11-17 · CALI-187 (#298) · a drag candidate's mesh read straight off OCC: 10× on a study, the same numbers

The foreman's aero speed slice, from reviewer-2's walk: 0.916 s a candidate, 95% of it the CAD rebuild.

**Where the rebuild goes** (the camper sample's cargo box, unloaded, median of 5):

| step | time |
|---|---|
| `build(params)`, the ruled loft | 0.013 s |
| CadQuery's `tessellate(0.5, 0.2)` | 0.278 s |
| … of which OCC's mesher (BRepMesh) | 0.013 s |
| … of which the Python copy, `for t in poly.Triangles()` | 0.265 s (cProfile: 0.285 s for 728 triangles over 98 faces) |

So the time is CadQuery copying the triangles out, not building, and not meshing.

**Now:** `caliper.tess.triangles(shape, tol, ang)` meshes as `tessellate()` does, then reads each face's nodes and
triangles by index. The build worker's answer goes through it (`_build_worker.answer`). The output is the same arrays,
element for element:
- the face's Location applied to its nodes;
- a reversed face's winding flipped;
- a face with no triangulation skipped;
- a compound's every solid.

**Skin only:** nothing to do. The cargo box's `build()` is one loft, and the worker only ever calls `build()`, never
`construction()`.

**Not done: a pool of build workers.** `ParametricStudy.sweep` at the pin (25e282e) takes no `workers`, so it needs a
whittle PR first. With `workers`, scipy's differential_evolution also switches to `updating='deferred'`, so the search
would find different designs. The foreman's call: it waits, to be re-decided on what's left.

**Measured:**
- **A drag study, before and after** (scratch copies of the camper sample; 8 numbers, the sample's own bounds, the
  Leaf as obstacle, 2 stations, effort 0.17; load average 4.5–5):

  | | wall | builds | a build |
  |---|---|---|---|
  | main | 261.5 s | 289 | 0.905 s (reviewer-2's 0.916) |
  | this branch | 26.2 s | 289 | 0.091 s |

  The records' stations (each design, its drag and force) and notes are identical.
- **One tessellation, CadQuery against the direct read,** identical at both tolerances. Theo's are scratch copies,
  deleted after:

  | part | faces (reversed) | 0.5 / 0.2 | 0.05 / 0.1 |
  |---|---|---|---|
  | cargo box | 98 (97) | 0.292 → 0.017 s | 0.287 → 0.023 s |
  | Theo's bar stool (i-want v8) | 199 (66), cones, cylinders, tori | 0.620 → 0.070 s | 0.789 → 0.170 s |
  | Theo's step-stool-5 v12 | 22 (15) | 0.065 → 0.005 s | 0.066 → 0.005 s |

**Next PR (the foreman's call):** move `measure._cadquery_to_trimesh` (every build and check), `pieces._meshed` and
features.py onto the helper, with their own around runs.

**Tests** (tests/test_tess.py, 19). Each failed at 700739d (no `caliper.tess`), run from a scratch tree:
- np.array_equal against `tessellate()`, at 0.5/0.2 and 0.05/0.1, on:
  - the cargo box and the step stool samples;
  - #332's tube and clip;
  - the holed panel;
  - test_tipping's bar stool.
- the fixtures checked for what they must cover: reversed faces, cylinders, B-splines;
- a moved shape;
- a compound;
- no faces;
- a face left bare;
- the worker never calling `tessellate()`;
- a real BuildWorker's mesh.

**Mutants (11), all caught on the first pass:**
1. no flip for a reversed face
2. flipped the wrong way
3. the face's location ignored
4. no offset
5. one-based
6. a bare face not skipped
7. offset by triangles
8. no faces crashes
9. float32 vertices
10. the angle dropped
11. the worker back on tessellate
