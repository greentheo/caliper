### 2026-11-07 · CALI-94 (#106, with main's #124, #132, #136) · The middle foot only, through the one verdict
- **Merged forward** onto main's one verdict (#132): #106's hand-written "middle only" checks become `edge=` on
  `verdicts.case` / `run` / `goal`, and each reader asks those: the part card ("A kid stepping up: checked in the middle
  only; …", never "Holds …", which #132's guard now catches), the design card and scorecard (`edge` status, its
  note), Studies (its count said), the chat's facts, the build book's cell and the kid's book (each case's verdict),
  the picture's re-check, the history line (the run's verdict; `middle_only` kept for older readers) and the page
  (the server's verdict; the callout keeps "the middle read …; the front edge, where people stand, isn't checked").
- **The carve tests stay light** (5604868: the carve's mechanics on the middle foot alone, for CI's hour). The
  carve-down's kid stage stays on the middle foot: at 60 lb its front-edge foot fails as drawn (1.91x), so it can't
  carve down from holding; #105's repro on both feet (40 lb) is #124's own slow test.
- `test_edge_foot.py` reads the verdicts (the page's helpers are main's).
- **CI on 09cbb07:** `test_carve_closed`'s open-join test carved #106's MIXED, now with the front-edge foot: its
  two-load carve's step 1 doesn't close (#105's kind, rightly refused: `closed: False`) and the whole part fails at
  the edge, so there was no step 1 to force open and `best` was 0. The test means a carve whose step 1 closes: it
  carves the middle foot only (`CENTRED`, main's MIXED), and says why.
- **The review's sweep of every reader (with main through #144):** Studies' headline judged a run with no edge ("holds
  — weakest a kid stepping up: 3.1x", green); it now reads "middle only — weakest …; the front edge isn't checked",
  not green (`consistency.middle_only`: the run's own history line, else the part as it is now). The design card's
  history line (#138 item 3's reader) and #140's "last checked on vN" line carry it too ("…: 3.1 times over, checked
  in the middle only · v5 not checked yet."). `_times(x, about=False)` owns "about": 10 or more is "more than 10 times
  over", never "about more than 10" (#144 review). Each pinned; the mutants (no edge to Studies, to the history line,
  to the last-checked line; "about" before "more than") fail them.
