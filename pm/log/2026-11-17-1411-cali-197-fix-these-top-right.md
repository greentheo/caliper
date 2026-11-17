### 2026-11-17 · CALI-197 (#331) · item 6: Fix these is the part's, top right, now that #322 is in

The foreman's item 6, after #322 and #338 merged (main a484d28).

**Main merged in** (1e12f59). One hunk in design.js: #331's `fixesSection` and `fixFresh` against #322's `fixGo`,
`fixPicked` and `fixesBox`. Kept `fixGo` and `fixPicked`, took `fixesSection` in place of `fixesBox` (nothing draws it
any more). The test harness was wrong, not the code: main's `fixesView` now calls `fixGo`, so test_part_panel_marks'
stubs gained one.

**Fix these, top right** (#325: "Fix these, where the list has ticked rows"):
- **`fixAct(part)`** draws it last on the part's bar, after the cut plan, as #325 lists them. It's there only where the
  list is read for this version and its newest check (`fixFresh`) and has rows, the list's or your own.
- **Greyed while nothing's ticked**, with why on hover and on tap: "nothing's ticked in Things to fix". It counts what
  `fixPicked` sends, so an open question left unticked (#318) is nothing to fix until you tick it.
- **"Fixing…" while it runs**, off, from the list's own `running`: a fix job isn't in the server's running list.
- **Pressing it** opens Things to fix (`GO_OPENS.fixGo = ['work', 'fix']`), then asks the plan (`fixPlan`, the request
  the list's button made). The plan's cost, Go ahead and Not now are said in the list, as before. A refusal is said there
  and the button comes back.
- **`paintFixAct`** draws it again, alone, as the list lands, on a draw, and on every tick, yours or a row's: the other
  buttons keep their wiring. Only the part in view.
- **The list's own Fix these is gone:** each action has one place.

**Tests** (tests/test_fix_act.py, 11 new). Each failed at 1e12f59:
- last on the bar where the list has ticked rows;
- none where the list isn't read, is stale, failed or is empty;
- greyed with why while nothing's ticked, and not once your own row is;
- an open question left unticked is nothing to fix until it's ticked;
- "Fixing…" while it runs;
- `GO_OPENS.fixGo` read from the page;
- pressing it posts the plan for what's ticked, and the list is painted with it;
- a refused plan says why and the button comes back;
- drawn again alone, one of it, and only for the part in view;
- the list's paint, a draw and both ticks draw it;
- the list has no Fix these of its own.

**Changed with the code:**
- test_fix_these: the idle list has no plan button now;
- test_part_panel: `GO_OPENS` with `fixGo`, and `BAR` stubs `fixAct` (`BAR_ONLY` is the bar without it);
- test_part_panel_marks: `paintFixAct` stubbed where `paintFixes` and `wireFixes` run.

**Mutants (20), all caught on the first pass,** each run against test_fix_act, test_fix_these, test_part_panel and test_part_panel_marks:
1. a stale list's button
2. an empty list's button
3. never greyed
4. every row counted, ticked or not
5. no running words
6. no running label
7. not on the bar
8. opens nothing
9. any part's bar
10. the old one left
11. never wired
12. posts nothing ticked
13. a refusal unsaid
14. the button never back
15. the plan unpainted
16. the list's paint without it
17. a draw unwired
18. a tick unsaid
19. your own tick unsaid
20. the list's own button back
