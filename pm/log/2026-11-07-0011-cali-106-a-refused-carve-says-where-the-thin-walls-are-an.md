### 2026-11-07 · CALI-106 (#101, #136 review) · A refused carve says where the thin walls are and what to change
- **Where:** `measure.thinnest_wall` returns the thinnest wall and where it is (the middle of its ray);
  `min_wall_thickness` is its number. `load_study._thin` says which it is: a piece by name, or a measured wall's
  place. The strength record carries `thinnest_where`.
- **What to change:** `load_study.thin_words`, in the design's units: the wall, where, the size the strength check
  sees walls from at this size, a 0.4 mm nozzle where it's printed and thinner, and the part's own `min_wall >= …`
  rule (`wall_rule`, its spec's or the design's, read with `safe_eval`); otherwise "Thicken them first."
  `resolution()` carries it (`said`, `where`), the carve refuses with "Can't carve it by strength: …", and a too-thin
  check stores it as `thin_said`, which the page's disabled Carve and Lighten say.
- **One wall number** (#137 item 2, the same words): under 1 mm, two places, in `answers._wall` and the page's
  `wallLen`. The bar stool's 0.25 mm wall read 0.2 mm on the card and 0.3 mm on the page.
- On a copy of Theo's bar stool v7: "its 0.25 mm walls around z 16.1 in … Your rule shell_wall_thickness says at
  least 2.85 mm: thicken them to that first." z 409 mm, r ≈ 169 mm: the webs between the openings, where the
  foreman found them.
- Tests: tests/test_coarse_steps.py (+5: where, the line on the spool and on the stool's numbers, the refused carve,
  one wall number on both sides, the page's blocked carve). Touched suites: 187 passed locally; CI is the full run.
