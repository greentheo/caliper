### 2026-10-30 · CALI-67 (#27), CALI-69 (#29) · Panels that fit the design, and a description that keeps up
- **Theo,** walking through the strength check: the rough edges I'd listed were his feedback ("the whole
  interface is a bit complicated… how can even my 6 year old make something while still being useful for a
  real mechanical engineer"), then "proceed with #27 and #29".
- **#27, one rule for drag:** `studies.in_air()` reads the design's prompt, requirements and part
  descriptions for a vehicle, a road speed or wind (car, trailer, hitch, cargo box, mph, wind…; not "towel"
  or "window"); a reference part (the car) or existing drag studies also count. Without it, **Shape it for
  drag** and **whittle carving** are gone from the part's panel, and the Studies menu says why ("nothing in
  the design says it moves through air … say so and the drag studies appear"). The design's **Weight &
  balance** shows the hitch, its moment, the payload box and the lb·in columns only when a part declares
  where it's held; otherwise it's the weight and the red dot. The balance no longer adds "No part declares
  supports() — no hitch point". New-design placeholder: a step stool, not a cargo box on a hitch.
  Stool: Size, Rules, Will it hold?, Built from, History. Cargo box: unchanged (hitch 2,103 lb·in, drag).
- **The strength view's rough edges:** **Will it hold?** moves above **Built from** (it was under the cut
  plan). The colours are brighter (blue to red, not navy to fog) and the centre-of-gravity dot steps aside
  while they show. The bar says which number is which: the colours are whittle's FEA (0–2.8 MPa on the
  stool) and the verdict is the plate check's (4.8 MPa, grain the wrong way), with the breaking load.
- **#29:** after every revision, `chat.redescribe()` asks Claude for the part's one-line description from the
  old one, the change and the new script (unchanged if still true, nothing the script no longer builds);
  offline, the old one with "(revised: …)" — the latest change only. Live, on a copy of the stool: "A
  two-step stool … two treads, … a back brace, and a middle riser" became "A single-step stool … two side
  panels, a front panel, a back panel, and a top tread, standing 10 in tall" after "make it 10 in tall".
- Tests: `test_studies.py` (+1: the stool isn't in air even with a towel rack by the window; a cargo box,
  a wind turbine, something behind a car and a design with drag runs are), `test_chat.py` (+2: Claude's
  new description lands and the conversation reads it; offline it says what changed, latest only).
  **Full suite: 473 passed.**
- Commits: `cf163fa` (#29), `e29472c` (#27), on PR #33 (stacked on #30).
