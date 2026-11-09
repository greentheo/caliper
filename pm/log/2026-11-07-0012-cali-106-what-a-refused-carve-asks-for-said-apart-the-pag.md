### 2026-11-07 · CALI-106 (#136 review, round 2) · What a refused carve asks for, said apart; the page keeps it off
- **The line asks two things apart** (thickening to the rule's 2.85 mm doesn't unblock a carve): printing and the
  part's own rule, "too thin for a 0.4 mm nozzle to print and for your rule shell_wall_thickness (at least 2.85 mm):
  thicken them to that"; and the strength check, in mm, "For a strength carve, walls must be at least 9.2 mm at this
  size, so check it by hand or with a test piece instead". With no rule and nothing printed, only the second.
- **The page keeps a blocked Carve off** after a job ends (`paintCarve` set `disabled` from the job alone, so a cancel
  re-enabled "Carve it again"), and a refusal reads without its exception's name (`plainly`: no "ValueError: …").
- **Lighten on a coarse run** says "Not resolved yet: the check was too coarse to see its walls…" (or "Not checked"),
  from the steps' `lighten_step` verdicts, as Studies does; it said "Nothing lighter still holds", a false ✗.
- Pins for the review's survivors: a coarse fail stays a fail (`carve_step`, `lighten_step`), and Lighten's `disabled`.
- Tests: tests/test_coarse_steps.py (16; 4 of the new fail without this, the fifth pins a fail). The review's last two
  pins: a coarse fail stays a fail with the whole part holding (`whole_holds: True`, where the whole-holds branch can't
  mask it), and the page's own refusal goes through `plainly()` (raw `e.message` fails it).
