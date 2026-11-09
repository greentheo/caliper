### 2026-11-07 · CALI-108 (#108, the backend) · A part's exact numbers, set by hand, with no Claude call
Theo, on the bar stool: "the advantage to manual cad is the ability to specify things precisely". The panel's UI waits
for his look at the mockup; this is what it calls.
- **`GET /api/designs/{slug}/parts/{pid}/params`** (`params.listing`): each `PARAMS` entry in plain words (its comment,
  or the comment line just above it), its value (mm for a length), its unit, its `RANGES` bounds, and whether the build
  reads it at all.
- **`POST …/params`** `{name, value, unit}` (`params.set_value`): inches (or ft, cm) to mm, stored in mm; a value
  outside its range refused, the range said ("wall_t must be between 3 and 12 mm: 20 mm is outside it"), nothing
  written; built first through the override path (#3c), so a value it won't build with isn't written; then only that
  `PARAMS` value rewritten by its source position (`aero.write_params`, `keep_float`: "6.0" set to 5 is "5.0"), its
  comment and every other line exactly kept; a new version whose history says "set wall_t to 5 mm by hand" (and the
  old and new numbers); the design measured again. No Claude call.
- **A value the build ignores or clamps is said:** the part's shape didn't move ("its build clamps or ignores fillet_r
  at 8 mm"), or `build()` never reads it.
- **The accept, on a copy of the bar stool:** its v5 restored (as v8: Theo's is at v7), `wall_t` set to 5 mm gives
  v9 with `"wall_t": 5.0, # printed shell thickness mm (increased from 4mm)`, rebuilt in 20 s and the design
  measured, no API call; 20 mm refused with its 3–12 mm range.
- Tests: tests/test_params.py (7: the listing, the rewrite, a version with no Claude call, inches, the range, ignored
  and clamped values, the API). Stacked on #143.
- **With #143's rework:** the by-hand edit and the skeleton's drive share one rewrite (`aero.set_params`), and the trial
  build is from the script's own `PARAMS`: builds never override (#143, the foreman's call).
- **#147's review:** what a number is, by what its script says (never by 6 vs 6.0): a length by a length unit in its
  comment, a length's name (`wall_t`, `fillet_r`) or a length word in its comment ("width of the box"); a count
  (`mesh_rows`, "how many"), a ratio (`taper`, `infill`) or an angle by theirs. Only a length converts: "mesh_rows 8 in"
  is refused ("mesh rows is a count: give a number, no unit"); a number with no known unit is taken as it is, and said.
  No `RANGES` for it is said ("no range is set for fillet_r in the script, so it isn't checked"). A part with strength
  runs says "strength: check the box again". A partial clamp is measured: a fillet's or hole's radius from the built
  solid's cylinders ("asked 3 mm, built 2 mm (the closest fillet)"), a wall's thinnest measure; elsewhere "its shape
  changed; whether its … isn't measured". The POST answers with `notes`. Tests: 14 (5 new, 9 failing before).
- **#147 re-review, on Theo's own scripts (the foreman's order):** a length unit in the comment wins (`rib_v`, "vertical
  rib between rows mm", is a width, not a count); a comment that lists choices ("1 = straight, 2 = round") is a
  `choice`, no unit (`shoulder`, `tail_curve`, `edges`, `spine_back`); then an angle, a count or ratio, a length by its
  name or words. **A number of no known kind refuses a unit:** "set p1z to 26 in" (leaf_rear, no comment) is "I don't
  know if p1z is a length: give it in mm, without a unit", never 26 written as mm; without a unit it's taken as it
  is, said. Tests: 30 (Theo's names and comments as the review quotes them, read-only; a count by its comment alone;
  p1z refused; a choice takes no unit). Mutants caught: count words in the comment ignored, the unit's order, a unit
  dropped.
