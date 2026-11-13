### 2026-11-12 · CALI-172 (#268) · Lighten keeps solid wood at joints, a run on an older version stays found, holed walls are checked for buckling

Theo's step-stool-5, live. His Lighten run on v3 (51 minutes, 19 steps, down to 7.37 lb saved) cut through the wood where
the bottom stringer passes through the sides. And when it finished he couldn't find it.

1. **A rim round every joint, not only the outline.**
   - What's checked: each panel cell is probed just past each face against every other piece (`_contacts`, with
     `consistency.slab_distance` and `segment_distance`). That catches a piece passing through (a stringer's mortise),
     set into it, or on either face (a cleat, a rail, a grip).
   - What it does: those cells, and everything within 1.5 in of them, are rim. The holes are clipped to keep 1.5 in
     clear of them too (`keep_out`), as they are for the outline. Hole-saw sites in a panel stood on keep off them too.
   - **On a scratch copy of Theo's v3 script** (run locally, not committed), the nearest wood Lighten may cut, to the
     bottom stringer:
     - in each side: 0 mm on main, 42.1 mm now;
     - in the stringer itself, by each side: 21.4 and 23.0 mm on main, 45.2 and 42.1 mm now.

     The rim is 38.1 mm.
2. **A run on an older version stays findable.** The run wasn't lost to its version.
   - The cause: Theo's v4 put printed fillet strips in the stool. The part then read as printed, the page drew a
     printed part's carve panel in place of Make it lighter, and the v3 run wasn't drawn anywhere.
   - Now the Lighten panel shows on any part with a Lighten run (`lightenShown`). It says "Lightened v3; you've changed
     it since (v4): Lighten it again, or look at v3's steps below (they can't be cut into v4)", or what blocks a new
     run. The steps stay viewable; the bar already refuses to cut an older version's.
   - A running Lighten (or strength check) records the version it's of. When the part changes under it, its progress
     line says so at once: "You've changed Step stool since this started (it was v3, it's v4 now): its steps will be of
     v3. It's kept, under Make it lighter."
   - Checked in the page on 8016 with a copy of step-stool-5: the v3 run, its 18 steps and that line are back.
3. **Each step's holed walls get the hand buckling check (`holed_buckling`).** A wall with holes is taken at its
   narrowest strip of wood across the load, over the whole remaining width (the safe side of splitting it). The
   foreman's call (a), on the numbers below:
   - where the solid wall had a held side, the strip is held on that side and free at the hole: Timoshenko's
     one-held-one-free case, `k = 0.425 + (b/a)²`;
   - with no held side (Theo's stool's sides), a column, braced or swaying as its row says.

   The row says which model it used ("the strip beside the hole, held on one side"). NEEDS ENGINEER CHECK (#42) is in
   the docstring.
   - A wall whose strip can't be found says "not checked: it has holes…".
   - The case's safety and what governs follow. The run's notes no longer say each step "doesn't check buckling".

**Tests:** 18 in `test_lighten_joints.py` on a synthetic stool with a through-stringer, a cleat and a grip, plus page
functions in node. One is a real one-step study (about 2 minutes). All 25 mutants are caught. Survivors at first, now
pinned or simplified:
- the room guard;
- the outer face;
- an unreachable direction check (simplified);
- the study's call;
- the panel's wiring.

**The model, on test_lighten's box stool** (its side wall, the first step's holes leaving a 125.4 mm strip of 254). As
first built, as a free column everywhere, it read 1.53×; step 1 failed and the study stopped, where on main step 1 holds
by the FEA. So the numbers went to the foreman:

| reading | each wall the whole load (asked on) | half each, since #265 (pinned) |
|---|---|---|
| solid, as checked (both sides held) | 44.73× | 89.47× |
| column of the strip, sides free, sway | 1.53× | 3.07× |
| **strip held on one side (used)** | **16.26×** | **32.53×** |
| strip with both sides held | 90.38× | 180.78× |

`main` (with #265) is in: on this branch the box's two side walls share the top's load by the lever rule, so each
number is twice the one the call was made on. The test pins the current four, with why, so a later change to the model
is a visible change.

**The around-file failures at first:** `test_running` (24) and `test_coarse_steps` (1) were stub pages missing the new
`changedUnder` and `lightenChanged`, plus `_running`'s row now carrying `version`. Those were the tests' fault, and no
expectation moved beyond the new key. `test_lighten`'s two were the column model above; they pass on (a).

All 30 mutants are caught: one more survived at first (a braced holed wall) and now has a test.

After the merge from main and model (a): the Lighten, Lighten-floor, coarse-steps, running, braced-walls, buckling,
load-study, carve-stale and use-it-margin files pass, 203. The verdict guard (`test_verdicts`) caught `holed_buckling`
setting the case's `holds`; it's a producer, as `check_load` is, and is marked so.
