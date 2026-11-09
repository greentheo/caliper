### 2026-11-09 · CALI-100 (#92, the server side) · Make it better on Will it work?, and Carve on the Studies page
Theo, on the bar stool: "Where is the card for reducing mass using stress loading and 3d printable shapes and such?"
The carve and the lightening lived one click down, and Studies never listed Carve.
- **Make it better** (`caliper.better`): each part's *Will it work?* ends with one line per improvement it can take
  (`better: True`), and a one-part design's card carries them too, so nobody has to select the part first.
  - **It fails as drawn:** only what would make it hold: a thicker sheet from the plate check's own numbers, offered
    only if every failing load is one the plate check governs, and not on a filled-in shape or with the front edge
    left out. Never something lighter.
  - **Results first, the cheapest first:** a thinner sheet that still holds every load on that panel by the plate check
    (a panel with a load the FEA governs is left out), then a carve's or lightening's step that holds, to use.
  - **Then invitations,** with what they take: a carve ("at least about 45 min at this size", from its check) or a
    lightening, only where `load_study.blocked` allows it, the one test the Carve button reads (#144).
  - **No unsettled number:** a result is quoted only when the part's own check holds as a settled verdict (not middle
    only, too coarse, on a filled-in shape or of an older version) and the step itself holds. Said with `_times`.
- **Studies** lists Carve for a part with a printed piece, with a why-not otherwise. Lighten's why-not on a printed
  part reads "it has no sheet pieces: a printed part is carved". Both read `blocked`, so Studies can't offer what the
  button refuses.
- **The page is minimal until Theo's seen the mockup:** the lines are ordinary card lines that go to the strength
  panel, where Carve, Lighten and "Use" already are. No new controls.
- Tests: tests/test_make_it_better.py (11). Mutants (ignoring `blocked`, no settled filter, invitations first) each
  fail one.
