### 2026-11-20 · CALI-220 (#375) · the studies read a part in its own frame; a run's overlays draw where it is now

The foreman's must-fix ahead of #374 (Copy…/Move…). The strength check voxelized the POSED mesh
(`store.part_geometry`), while a script's loads(), HELD and construction() pieces are in the script's own frame.
Nothing applied the pose. Every checked part had sat at pose 0, so it never showed.

**Measured on main:** LEGGED moved 300 mm and turned 90° reads ✓ 2.14 by its plate check, with no joints read. Unmoved,
it fails ✗ 0.5 at a joint. That's a false ✓.

**The choice, agreed with the foreman: the part's own frame.**
- `store.part_local(pid)` is the part unposed, beside `part_geometry`. `store.part_pose(pid)` is its pose.
- Every study that pairs the build with what the script declares reads `part_local`:
  - load_study's voxels and sides, and through `prepare`, Lighten, Carve, the picture checks and coupons;
  - consistency (the pieces against the build, the covers, the panels' words, a bare edge, cut-smaller);
  - construction (the printed rest, the fasteners, the keeps);
  - joints, joint_check, marks;
  - tipping (its footprint, against a centre of gravity reckoned from the declared pieces);
  - trials, pictures, and scenarios' touch checks.
- **Why not transform the inputs:** a load or support box is axis-aligned. Under a turn that isn't a quarter turn it
  stops being a box, and forces, outlines, stick ends and holes would all need turning too.
- **What keeps the posed mesh,** because it's about where a part sits: fit between parts, mirror, aero (whittle's drag
  carve runs on the posed STL), chat's seating, the build plan, the design's bounds.

**The viewer, the foreman's option (b), in this PR:**
- A run made in the part's frame draws where the part is now, by one matrix, the part's current pose (`partPose`,
  `overlayPose` in design.js).
- **The part-frame kinds:** load, Lighten, Carve and the frame study. The heat, load box and arrow move as a group. A
  station's geometry is posed, but not its ghost, which is the posed part already.
- Runs made before a move were all at pose 0, where the part's frame is the design's, so they draw on the moved part
  too.
- `design_state` sends each part's `position` and `rotation`. caliper-ui has the exact lines.
- The scenario editor's boxes are in the part's frame on the server. Drawing and dragging them under the part's pose
  is caliper-ui's #296 B1.

**Pinned** (`tests/test_check_own_frame.py`):
- **LEGGED moved and turned:** the same as unmoved, case by case and joint by joint.
- **Every declaration-paired check reads the same moved:** consistency's checked, joints, marks, tipping, construction's
  report, pictures' panels.
- **A scenario saved on a moved part** (1,000 mm away) is on the part, and the check reads it.
- **The viewer**, with the vendored three.js in node:
  - `partPose` is the server's `pose_matrix`;
  - a point from a run made before the move lands on the moved part's;
  - only part-frame kinds are posed;
  - both overlay sites apply it, and the station's ghost isn't posed twice.
- **A guard:** none of these modules reads `part_geometry`.

**Fail first on main:**
- the moved stool: ✓ 2.14 by the plate, against ✗ 0.5 at a joint;
- the broad pin (consistency's checked differs);
- the scenario save: "doesn't touch the part: it pushes on thin air, 250.0 mm from its nearest surface".

The scenario test first moved the part only 300 mm, and passed on main: the turned top still lay over the box. The test
was wrong, so it now moves the part clear.

**Theo's step-stool-5** (copies, today's v16): moved 300 mm and turned 90°, it reads the same as unmoved, every case
(3.86, 3.8, 14.5) and joint. That's identical with main's code on the drawn copy. Copies deleted.

**Mutants:** each of the 21 switched reads put back to the posed mesh, one at a time.
- **With the guard:** all 21 caught.
- **By behaviour alone:** 6 caught: the strength check's voxels (load_study), consistency's checked and covers, the
  joint check, and scenarios' touch check.
- **The other 15** read the same on LEGGED either way, so only the guard pins them:
  - joints and marks take their geometry from the declared pieces, and the mesh only says which side a sheet's
    thickness goes;
  - LEGGED has no tip case, no picture and no fastener estimate, so tipping, pictures and the fasteners are empty;
  - the rest are words, or a read only some parts make.

**Full run** (`-n 4`, not serial; meant as an area run, but macOS's bash 3.2 has no `mapfile`, so it ran everything).
Seven failures, all in tests, none in the code. The stand-in stores in test_tipping (three) and test_stray_faces
replaced only `part_geometry`, and these checks now read `part_local`. Each stand-in gives both now, and both files are
green. **Full suite: CI.**

#### Round two (caliper-reviewer on #389)

Four more readers paired the POSED mesh with what the script declares. Each now reads the part in its own frame:
- **`patterns.pieces`:** its middle, which says each piece's outside face. On step-stool-5 moved 300 mm, at 90° the
  bottom stringer, middle rail and both cross rails were drawn mirrored, and at 30° the back rail, all still labelled
  "outside face". That's CALI-86's mirror, back.
- **`kidbook.make`:** its sides, so its screws. They dropped from 49 to 45 moved.
- **`answers.part`:** `plan_differs`.
- **`chat._edge_said`:** its pieces' sides. The seat and twin points it tests against them were picked on the posed
  part, so they get the inverse pose on the way in. Otherwise the pieces and the points would still be in different
  frames.

**Pinned:**
- **Patterns:** a moved part's patterns equal its unmoved ones, at 90° and at 30°.
- **The kids' book:** moved, it drives every screw the shopping list counts, as unmoved.
- **Euler order:** the viewer pin now turns about three axes, [20, 30, 90]. The 'XYZ' to 'ZYX' mutant is caught.
- **The guard grows:**
  - `patterns` and `kidbook` whole;
  - `answers.part` and `chat._edge_said` as functions, since those modules also, rightly, read where a part sits.

**Two of my test slips:**
- **The pins first moved the part 300 mm, and passed on the old code:** these symmetric stools' posed mesh still covered
  their own. That made the pins worthless, so they move the part 1,000 mm clear now. Then all three fail at 8556cb3 and
  pass with the fix.
- **The patterns comparison** first tripped on a page's drawing function, made fresh each call. The comparison skips
  functions now.
- **Area tests:** green at `-n 4`, the 25 files that drive patterns, the kids' book, the part card and the mirror
  seating. **Full suite: CI.**
