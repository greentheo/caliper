### 2026-11-09 · CALI-108 (#108, the screen) · The Parameters panel: exact numbers by hand, no Claude call
Theo, on the bar stool: "the advantage to manual cad is the ability to specify things precisely". The server side landed
in #147; this is the panel, to the mockup he approved.
- **Each number of a part in plain words** (its comment; its name where the comment is only a quantity, "12 in"), its
  value in the person's units (12.7 mm reads 1/2 in), its range, and whether its build reads it. Below the cards when
  a part is selected, and on the design's own view for a one-part design, so nobody has to select it first.
- **Type 3/8, 1 1/4, 12.7 mm or 2"**. A click selects the number so typing replaces it. A bad value says why and turns
  Rebuild off, with the range. Retyping the number shown isn't a change.
- **Rebuild writes everything changed as one version** (`params.set_values`, `POST …/params` with `values`): built once, all
  or none, so numbers that only work together can't leave a half-way part. The history says each one, and exactly:
  a rough "0.4 in" for 3/8 is gone from the record.
- It then says "v8 written: …", what the build ignored, and "check it again" where a strength check is now old.
- Not from the mockup: its "under X the check can't see this wall" and "too big for this flange" notes are particular to
  its example. The server's refusal or the card says these for now.
- Tests: tests/test_params.py (99, the page's through node). Mutants (no range check, range ignoring units, an unchanged
  number counted as a change, Rebuild on with a bad number, a panel on a reference) each fail.
- **#171 review:** after Rebuild the model on screen is the new one. The same number written differently (100.0 for 100, 0.375 for 3/8) isn't a change, on the page or the server. A measurement is said only when it's that one number's own: a fillet or hole radius this change made, one number at a time. A carved part has no numbers to set and says to roll it back. The panel sits right after *Will it work?*, a range shows on a change or a warning, and the written line uses the plain names as the mockup does.
