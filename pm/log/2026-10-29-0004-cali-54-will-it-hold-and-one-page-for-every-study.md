### 2026-10-29 · CALI-54 (#1), CALI-70 (#31) · Will it hold? And one page for every study
- **Theo:** "please launch and I'll take a look at the results! And I think we need a page in the app, or a
  menu to access all of these studies". Second slice of #1: a study for a part the designer writes.
- **`loads()` (and `held()`)** join the part-script reference: what pushes, how hard (`lb`/`kg`/`force`), a
  `factor` (2 for someone stepping on), and the box it pushes on; held at the floor unless it says. The
  designer is told to write it when the requirements name a load. A new check, `loads_land`, fails a round
  whose load box doesn't touch the part ("… 40 mm from the part — put its box on the face it pushes on").
- **`load_study.py`:** whittle's `LoadStudy` in-process, in the material `construction()` names (Caliper's
  own E and strength, so the BOM and the FEA agree), at 4 voxels through the thinnest piece (capped at 150k
  voxels). Per load: the FEA's peak *beside* the load and the floor (whittle's robust 99th percentile leaves
  the hardest-worked spots out: 1.9 MPa on the stool, against 2.8 where the top meets the front), how far
  it gives, where it works hardest, a stress picture on the part's own surface. And a **plate check** for a
  sheet pushed face-on that rests on other pieces all round (Roark Table 11.4, simply supported, the load at
  the middle; checked against Timoshenko and by hand), said both ways for plywood's grain, with every
  thickness sold. The verdict takes the worse; "breaks at" is load × factor × safety.
- **Why both:** measured on the stool's top at three voxel sizes, the FEA's numbers wander (deflection
  0.14/0.15/0.10 mm, peak 3.9/2.7/2.3 MPa) inside the plate formulas' range (2.8 clamped to 4.8 MPa simply
  supported). The fused voxel joints read stiffer than glued-and-screwed; the plate check is the safe side.
- **Live, through the chat only:** on the stool (v2), "It has to hold me too: 200 lb, stepping up onto the
  top." The router first called that an answer (it "changes no geometry") and replied with a summary; it now
  routes a requirement on a part to a refine. → v3 in 1 round: `loads()` exactly as the reference shows it
  (200 lb × 2, a 4 in foot in the middle), shape unchanged, every check passing. **Check it holds** (15 s,
  65,040 voxels of 4.8 mm): **holds, 3.1x** — the plate check on the top tread (14.5 × 8.5 in, held all
  round: 4.8 MPa → 6.2x with the face grain across the 8.5 in span, 3.1x the other way, sags 0.26 mm); the
  FEA puts the hardest-worked spot in the front panel where the top meets it (2.8 MPa, 10.9x). The thinnest
  ply that holds: 5/8 in (2.2x); 1/2 in doesn't (1.4x). The chat's reply now says the requirement went into
  `loads()` instead of "I can't make it a rule".
- **The Studies page (CALI-70, #31):** a header button; per part, every study and why it can't run yet
  (reference parts get none); every run newest first with the version it ran on (from the part's history
  when the run didn't record one), "changed since", and its one-line result; **Open** goes to the run in its
  panel, a strength check on its stress picture. `studies.py` builds it from the runs `design_state` loads.
- **Filed:** CALI-71 (#32), lightening a sheet part's panels with through-cuts a sheet can take (whittle's
  plate study per panel, checked in 3D), which #10's stool needs.
- Tests: `test_load_study.py` (6: the plate formula against Timoshenko and the hand number; loads parsing;
  a load in thin air fails the round; the stool with an overhanging top gets the FEA and no plate check; a
  box stool gets the plate check, grain both ways, thicknesses, breaking load; no loads, no study),
  `test_studies.py` (4), and the strength reply in `test_promote.py`. **Full suite: 470 passed.**
- Commits: `4e7d2a1` (strength), `1e17020` (studies page), `b7a2ef5` (docs), on PR #30.
