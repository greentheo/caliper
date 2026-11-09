### 2026-11-07 · CALI-122 (#137) · The bar stool's pre-flight: its broken rule said, where it fails, no carve on a fail
From the reviewer's pre-flight of Theo's bar stool v7 (a copy; nothing of Theo's touched), with the foreman's
correction: the run's "seat top" was a mislabel.
1. **A part's own rules, measured, with their verdicts** (`part_rules.measured`: once per version, in memory, nothing
   written). The page's *Rules on this part* shows each rule's verdict, and what it measured where it doesn't hold;
   *Design checks* falls back to the parts' rules. A rule it breaks leads *Will it work?*, on the part and the design:
   "✗ Breaks its rule shell_wall_thickness: its walls are 0.25 mm around z 16.1 in; it says at least 2.85 mm."
2. **Where it fails, and how sure.** The FEA's hottest voxel was named after the nearest *wood* piece even in the
   printed part: v7's "seat top" was at z 389 mm, in the cone's 0.25 mm webs (the foreman's v1 run too). `in` now
   names a piece only within a voxel of it, else the printed part, and the run records the wall there (`wall_mm`,
   measured within two voxels; a piece's own thickness). The line says where the worst stress is, in one run at its
   voxel size; the coarse caveat only where the walls there are too thin to see, otherwise the thin walls are said
   apart. An older run (no `wall_mm`) keeps the old words, and its label is never shown: the page's "works hardest
   in seat top" (Theo's v4 card on main) and a trial's "where" name a piece only from a run that recorded its wall
   (`peak_in`; the page says "around 27.8 in up" instead). One wall number, with where.
3. **No Carve, no Lighten, on a part that already fails as drawn** (`load_study.already_fails`, from this version's
   own check's one verdict): "Can't carve it: it already fails (0.5 times over, in …): make it hold first, then
   carve." The page's Carve and Lighten are off and say the same (`carveBlocked`, `lightenBlocked`).
4. **A carve says how long it has run** ("· running for 6 min"), repainted every 30 s: its sweep reports little before
   step 1. "the printed PETG (printed)" (P2 item 8) reads "the printed PETG".
5. **A goal says its limit:** "✗ Mesh cone keeps total weight down (assumed): 13.1 lb, over its 10 lb cap" on the
   card (`_against`), and "(cap 10 lb)" in the Score panel.
7. **A disc on a ring gets its own plate check** (Roark Table 11.2 case 16, `ring_plate`; the ring is the widest one
   the part beneath holds 90% of the way round, probed just under the panel). The bar stool's seat: ring 270 mm,
   4 in pad, 3/4 in ply: 4.57 MPa, 3.3x across the grain; the foreman's hand check gave about 4.5 MPa. A failing line gives it as a second opinion
   ("By hand, the seat top on its own, as a round plate on its 10.6 in ring: …"). The pad is measured in the panel's
   plane (the disc's frame ran diagonal, and read the 4 in pad as 119.5 mm). Never "only 16 of its 16 edges rest".
   NEEDS ENGINEER CHECK: the round-plate formula and the ring as its support.
- **The pre-flight again, on a fresh copy of the stool** (its strength check re-run, no live calls): "✗ Breaks its rule
  shell_wall_thickness: its walls are 0.25 mm around z 16.1 in; it says at least 2.85 mm." / "Doesn't hold 250 lb
  person seated: only about 0.5 times over, and it needs 2. Its worst stress, in one run at 3/16 in voxels, is in the
  cone skirt around z 15.3 in, among 7/32 in walls the voxels can't see: the fail may be the model's. … By hand, the
  seat top on its own, as a round plate on its 10.6 in ring: 3.3 times over." / "✗ … 13.1 lb, over its 10 lb cap."
  Carve and Lighten refused. Theo's own folder has no v7 strength run (its newest is v4): these read after he checks
  v7 again.
- The reviewer's nit on #132: a carved step that doesn't close up is an amber dot (#136 draws dots by verdict), pinned.
- Not here: P2 items 6, 9–12 (#89's wording pass), and a live first run (no key).
- **#139 review, the blocker:** `goalLimit` called `scoreView`'s own `num`, so a goal with a number threw "num is not
  defined" and blanked the inspector (a global stub in the test hid it). It's `scoreNum`, at module level, tested
  unstubbed with `scoreView` itself. A refused job reads without its exception's name: `follow()` passes the job's
  error through `plainly()` (main said "⚠ ValueError: Can't carve it…" since #136). *Show the stress* names the peak
  by `peakWhere`, never an old run's "seat top".
- **#139 review, items 4–7:** each wall number says which wall ("its thinnest walls, 0.25 mm around z 16.1 in"; "the
  worst stress is in the cone skirt around z 15.3 in, where its wall is 5.2 mm"), and walls and voxels are in mm
  everywhere, heights and positions in the design's units (`_wall`; the chat's small lengths keep their fractions,
  `_small_len`). The seat's ring is probed 1 mm under it in 1 mm steps and said as its outer edge ("held at its ring's
  outer edge (10.6 in across)": the cone flares to r 135 mm there). An older run's stored "only 16 of its 16 edges"
  is rebuilt from its numbers (`load_study.plate_why`). A refusal on a coarse run hedges as the strength line does:
  "its check says it fails (0.5 times over, a coarse run: the fail may be the model's; …): make it hold first".
- Tests: tests/test_preflight_bar_stool.py (17), and touched suites' expectations for the new words. Stacked on #136
  (its too-thin words), on #132's one verdict.
