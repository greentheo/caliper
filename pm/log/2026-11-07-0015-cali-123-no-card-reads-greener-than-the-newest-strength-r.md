### 2026-11-07 · CALI-123 (#138) · No card reads greener than the newest strength run
From the reviewer's cards-only re-pre-flight of Theo's bar stool on main (a fresh copy; Theo's folder has v1 2.58x,
v3 twice "0x", v4 1.7x ✗, and no v7 run).
1. **The design card takes the newest run, and says how old it is.** It said "! Holds a 250 lb person sitting, 2×
   safety (assumed): 2.58x (scored before the last change…)" from the v1 scorecard while the part card said v4 doesn't
   hold. `answers.measured` keeps the newest run of a part changed since (`strength.last`), and `held_to` says it over
   any older card's number: "✗ Holds a 250 lb person sitting, 2× safety (assumed): last checked on v4: 1.7x, needs 2x ·
   v7 not checked yet." A newest run that held reads amber with its age, never ✓; a card newer than the run still
   reads as the card.
2. **A stale scorecard's rows are no ✓.** The panel kept v1's "✓ holds … 2.58x", "✓ your shop can make every piece",
   165 h and Stock $101 under "a part has changed since". Now its passes are an amber "·" and every number says
   "(as of v1)", the header "Scored as of v1:"; a fail stays a ✗ (`scoreMark`, `asOf`).
3. **A check whose load never reached a support isn't a 0x ✗.** `verdicts.case` reads it `unchecked`, with its own
   reason ("nothing connects where it's pushed to where it's held"), so Studies, the part card ("…: not checked: …
   Check where it's held and pushed, then check it again"), the history line (from the run's own verdict, where the run
   is still there, so v3's older lines change too) and the scorecard all say so; its 0x never enters the design's
   minimum (`answers.ran_safety`).
4. **The cold /answers:** of the design cards' 89 s and the part cards' 115 s on the copy, ~39 s per call was
   PrusaSlicer, run as a subprocess for each printed piece (3), three times per /answers (`making.plan` from the part
   card, its weight and print time). `printing.estimate` now remembers what it sliced by the STL's bytes, material,
   printer size, infill and slicer: on the copy, 45 s for the first design cards (each piece sliced once, the rest is
   the state's builds) and 3 s for the part cards after.
- **#140 review:** the run's `safety` is written from the cases that ran, at the source (`load_study`), so the first
  run's step, the picture's re-check and Studies can't print 0.0x; an older record reads unchecked. Studies says an
  unsupported case's own reason, with no number ("not checked: nothing connects where it's pushed to where it's
  held"). A slicer that timed out (or wouldn't run) says so, not "no slicer installed", and isn't remembered. Pinned:
  the history's verdicts through `design_state`, `scorecard.compute` with an unsupported case, and the infill in the
  slicer's key.
- Tests: tests/test_newest_run.py (12; 7 + 2 fail without this, the rest pin what it keeps).
- **Merged with main's #139,** with the reviewer's asks from #139's pass: the scorecard row keeps both (`scoreMark` with
  "as of v1", and `goalLimit` through `scoreNum`); the page's blocked Carve and Lighten hedge on a coarse run, as the
  strength line does; the design card's hedge is the part card's (`fail_hedge`: the same wall, the 5.2 mm at the
  peak, not the 0.25 mm webs); pinned: a rule whose measurement errors is a fail (as `verdicts.report` reads an
  error, never a pass), `_peak_in` keeps `within`, `design_state` calls `plate_why`, and `study()` writes `safety`
  through `load_study.run_safety`.
