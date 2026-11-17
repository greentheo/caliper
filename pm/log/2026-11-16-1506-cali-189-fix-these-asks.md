### 2026-11-16 · CALI-189 (#322) · #318's small asks, in Fix these

The foreman's decisions on #318, added to #322:

- **"Gives first" only where a joint governs the case.** Where the plate check or the FEA governs, the governing joint
  "is the weakest joint under" the case; the others still "give too". The card never says a joint gives first in a case
  a panel decides.
- **Your loads are badged "your loads", not "measured".** A question about an edited load and a case turned off are the
  person's own edits: the rows say so.
- **An open question starts unticked.** It never settles itself: Fix these leaves it as it is and says so by name
  ("…; left open: you'd edited 'stepping on the front edge' to 260 lb; …"). Ticking it, then choosing, settles it.
- **Your own rows are kept per design.** They were already keyed by design and part; opening another design no longer
  throws them away.

Tests: 4 new (2 in test_fix_list, 2 in test_fix_these), 2 changed (the page harness reads `fixTicked`; the open-design
line). Each failed on the old source. 8 mutants, all killed. One test of mine was wrong on the way: it read
`scenarios.asked` as rows, where it gives words.
