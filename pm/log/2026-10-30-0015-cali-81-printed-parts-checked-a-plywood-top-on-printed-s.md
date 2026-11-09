### 2026-10-30 · CALI-81 (#53), CALI-82 (#54) · Printed parts checked; a plywood top on printed sides, carved
- **Theo**, mid-walkthrough: "what I was specifying was a plywood top and printed sides since the sides would work
  in compression and we could whittle them down more interestingly". The designer had printed the whole stool, the
  strength check couldn't analyse a print (no material), and first run hid that behind a "Check it holds" that
  failed the same way.
- **Printed parts (#53):** `load_study.printed_material()`, whittle's PETG/PLA at the share that's plastic (1.2 mm
  walls + infill) and at half strength across its layers. Voxels are sized from the part's thinnest wall. Labelled
  rough, on the safe side, until a printed test piece says (#42). A check that can't run is kept in the part's
  history, and the card and first run's reply say why. (Theo's printed stool couldn't be checked anyway: its loads()
  put the foot on the hand-hold slot.)
- **Mixed construction (#54, slice 1):** `{"kind": "printed", "rest": true}` is everything in the solid that isn't a
  declared sheet or stick. `construction.printed_solid()` is the part less its sheets and sticks (manifold), cached by
  script; weight, shopping list and the printer (just the sides, split to fit) read it. Consistency checks only that
  the pieces are inside the solid. The designer's reference says when to use it.
- **Two materials (slice 2):** greentheo/whittle#4 gives `VoxelFEA` a stiffness per voxel (element stiffness,
  preconditioner, energy and stress all scale; 189 tests pass), and `WHITTLE_REF` is pinned at its commit `65e7e59`.
  Voxels in a sheet or stick are that material, the rest printed, each judged against its own strength; an older
  whittle analyses at the printed stiffness throughout and says so. The plywood top's plate check uses plywood and
  counts an edge held where the printed solid is under it.
- **A beam check:** a panel held on two opposite edges (a top on two sides) is checked as a simply supported beam, the
  safe side, as the plate check is for one held all round. Before, the FEA judged it alone, reading stiff (its sides
  clamp it) and taking plywood along the grain. It says how much stronger it is with the face grain across the gap.
  It changes one verdict in the tests: the 14 × 10 in top on two sides, 3/4 in, is 1.5x across the grain and 2.9x
  along it, not the FEA's "over 2". A 1/2 in top over 12 in on two sides, as Theo specified, doesn't make 2x either
  way: the weak link a carve can't fix.
- **Carve (slice 3, `carve.py`):** whittle's sweep on the printed voxels only (the wood, where it's pushed and where
  it's held kept; any printed surface may open), each step judged by the strength check in both materials. The chart
  is the printed part's own safety and stops where it runs out; the whole part's is beside it, and a part that
  already fails in its wood says so first. Using a step writes the shape as the part's: the wood exact from the
  script, the carved rest less a lip round the wood (half a voxel proud), kept in `carved/` and named in the script
  (`CARVED`); `assembly._build_py_local` builds the part from it, and a chat revision drops it and says so.
  On a test stool (1/2 in plywood top on 20 mm printed sides, a kid stepping up), 3 minutes at 6 mm voxels: the sides
  go 13.6x → 15.1x → 8.4x as 40% is carved away, 644 g less filament, then come apart. The carved legs come out as
  arches with a foot rail along the floor, the plywood top exact, one watertight body.
- **The page and the chat:** **Carve it** under *Will it work? → the numbers* for a printed part, the chart, a
  preview ("Preview, not carved yet") and **Carve it like this** (then the strength check again); "carve the sides";
  the studies page lists carves.
- **A crash it found:** three requests for a mixed part's cards, making and balance at once ran manifold3d booleans
  on three threads and took the server down (SIGABRT), as OCCT did before it got its lock. Every manifold boolean
  now takes that lock.
- Tests: `test_printed_strength.py`, `test_mixed.py` (the printed rest is the solid less the plywood; the printer gets
  only the sides; its declarations check; two materials, with and without whittle's stiffness per voxel, and the
  beam; the carve: a top that fails says so, the sides carve down until they don't hold, using a step rebuilds it
  watertight with the plywood unchanged, a revision drops the carve; a sheet part can't be carved; the chat routes
  carve to a printed part only; carving through the API), `test_load_study.py` updated for the beam.
- Live check in a scratch app (port 8015): the carved stool in the viewport, the carve panel and its chart, a step's
  preview and **Carve it like this**.
- **Full suite: 543 passed** (with whittle at `65e7e59` and unfold-to-sheets at `8fc66c9`); after the lock fix, the 84
  tests it touches pass again.
