### 2026-11-07 · CALI-35c (#3c) · The skeleton's numbers drive the parts
#3's last slice: a planned design's shared numbers (the skeleton: "mast_top_z: 7 ft") drive every part that reads them.
- **The params override** (`assembly.skeleton_params`): a part's `PARAMS` key the skeleton names is built at the
  skeleton's value (`_build_py_local`, `part_geometry`, `evaluate`, `load_parts`; cached by the numbers it reads), and
  what it declares (`construction.declared`'s probe) gets the same numbers, so its pieces and loads move with its shape.
- **Changing one after the build** (`skeleton.drive`): the skeleton takes it, every part that reads it is written again
  as a new version (the same script, `action: skeleton`, the change in its history: no call to Claude), and the whole
  design is measured again. Its strength check, weight and score are then of the older shape, said as for any change.
- **In the chat:** after the build, "make the mast 10 ft" (a message that names a number) is the plan's revision
  (`P.revise`, one call); if only shared numbers changed, they drive the parts: "Changed mast top z from 7 to 10 ft.
  Rebuilt from it, with no new design: the mast, the hub. The design checks: …". A change to more than the numbers (a
  part, a check), or none, goes to the chat as ever.
- **A part that hard-codes a shared number** instead of reading it doesn't move, and the plan's rule pinning that
  interface fails, said (the drive isn't ok).
- Tests: tests/test_skeleton_drives.py (6, stubbed: the fake planner answers the plan and its revision; the parts are
  boxes that read the skeleton). No live runs.
- **#143 review (the foreman's call): no override at build time.** A drive writes each changed number into every part
  that reads it (`aero.set_params`, the same rewrite #147's by-hand edit makes) and saves that as a new version
  ("mast_top_z set to 10 ft (3048 mm) by the skeleton"); builds always use a script's own `PARAMS`, so nothing changes
  shape at the same version, and older runs go stale through the new version. (`assembly`, `design` and
  `construction` are back to main's: no `skeleton_params`.) A part reads a number only where the plan's rules name
  both (`skeleton.readers`), never by a key that only shares the name; one the plan says reads it but whose `PARAMS`
  hasn't got it is said and doesn't move. The inches guard: a default equal to the skeleton's old mm ÷ 25.4 is
  refused, with why. All or nothing: every part is built with its new numbers first; one refused or that won't build
  leaves the skeleton and every part as they were, and the reply says which and why. The reply names each part and
  the key it set, and "Strength: check it again on the mast" for each driven part with a strength run.
- **The name-collision pin:** the base, named in a rule of its own (`bbox(base).max_z <= 1`) but in none with
  `mast_top_z`, keeps its own `mast_top_z` key: not a reader, not rebuilt. Readers from any rule (the mutant that
  survived with the base in none) now fail it.
