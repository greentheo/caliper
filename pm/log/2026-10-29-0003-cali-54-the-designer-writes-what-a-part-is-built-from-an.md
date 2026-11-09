### 2026-10-29 · CALI-54 (#1) · The designer writes what a part is built from, and it's checked
- **Theo:** "go ahead and start on #1 with the stool". First slice: from a plain request, the designer writes
  `BUILD` + `construction()` (and `members()`/`supports()` for a frame) beside `build()`, and every build is
  checked against them.
- **One reference:** `src/caliper/part_scripts.md` documents every declaration (PARAMS/build, BUILD and
  construction, members/supports/jacks/GUSSETS/LAYOUTS, keeps, RANGES, shell/roof). The generator's system
  prompt carries it word for word (`authoring.system_prompt()`), plus a materials table generated from
  `materials.py`, so the prompt can't offer a material Caliper doesn't know. CONTRIBUTING points at it.
  `chat.TUNABLE` shrinks to a reminder to keep the declarations with the shape.
- **The check (`consistency.py`):** the sandbox runner now returns `construction()`/`members()` from the same
  run that built the part, and `authoring.improve` adds four measurements to every round:
  `construction_reads` (they run, with known materials), `construction_inside` (each piece's middle is in
  the solid; a tube's centreline within half its width, so hollow tubes pass), `construction_covers`
  (≥ 98% of the solid's surface lies on some piece, each sheet's thickness going one way, into the solid)
  and `construction_volume` (≤ 1.25x the solid). A failure fails the round with where it is, e.g.
  "9% of the solid's surface isn't on any piece: around (201, 250, 106), within … y 235..273".
- **Live, in the app (default chat, no script by hand):** "A step stool so my 6-year-old can reach the
  bathroom sink. Made from 3/4 in plywood, glued and screwed. It has to hold me too (200 lb)." → 4
  clarify questions (suggestions taken) → "build the stool" → v1 in 2 rounds, with `construction()` (six
  panels) written unprompted. v1 had a riser two sheets thick in `build()` and one in `construction()`; the
  first version of the check (two-sided thickness, 95%) let it through at 96.5%; the one-sided check fails
  it at 91.3%, exactly there. → "make the stool a single platform like we said…" → v2 in 1 round: five
  panels, inside 100%, covers 100%, volume 1.00. Built from: 8.9 lb, one 4x8 sheet of 3/4 ply + paint.
  Cut plan: 1 sheet, 12% used, all five panels nested (DXF, SVG, PDF).
- **The camper's hand-written parts pass the check as they are:** cargo_box (an envelope: covers 99.9%,
  volume 0.11) and frame (covers 100%, volume 0.94).
- **Router fix:** v1 was "a two-step stool" because the LLM router writes a new part's intent from the goal
  alone; it now sees the requirements and is told not to contradict them.
- **Not yet:** a study for a part the designer writes. Caliper drives only whittle's drag mode; "does it
  hold Dad" needs its load (FEA) mode with plywood, the person on the top and the floor as supports. Also
  found live, filed: the inspector offers a hitch rating and a drag study for a bathroom stool (CALI-67,
  #27); a promoted test reads a 19.05 mm sheet measured at 18.98 as a miss (CALI-68, #28); the part's
  description stays "two-step" after it's made single (CALI-69, #29).
- Tests: `test_consistency.py` (10: a stool that matches; a panel left elsewhere, one left out, one built
  thicker than its sheet, a sheet listed twice as thick; a declaration that raises or names balsa; nothing
  declared; a hollow tube frame; a mismatch failing a round with the fix in the feedback; the prompt
  carrying the reference and every material) + the router test.
