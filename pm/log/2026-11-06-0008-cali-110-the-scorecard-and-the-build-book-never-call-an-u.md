### 2026-11-06 · CALI-110 (#110) · The scorecard and the build book never call an unresolved ✓ a pass
- **The scorecard:** a strength check that would pass on a run whose FEA governs a ✓ it can't see the wall for is
  `unresolved`: never pass, counted with the unknowns (`summary["unresolved"]`), with the cards' own words as its
  note. A ✗ by its number stays a fail. `untrusted` (#96, a filled-in shape) is as it was.
- **So nothing downstream calls it ready:** the release isn't ready (`unknown` > 0). The book's header reads "Not
  ready — 1 not resolved", its scorecard table marks it "not resolved", and its *Will it hold?* row reads "not
  resolved: too coarse to see its walls". The Studies scorecard row isn't green ("· 1 not resolved"), and the
  release row says "not ready: a strength check isn't resolved". The page's scorecard shows "!" and "(1 not
  resolved)".
- **The design card's scorecard line** (#103's) names it "N not resolved", apart from "not checked yet".
- **The kid's book promises nothing on it:** no "It should hold…"; "Don't stand on it yet", for a grown-up.
- **From #111's review, four more places that said "holds"** on it, now fixed:
  - the 3D stress callout reads "not resolved: the FEA read 3.5x, too coarse to see its walls", with no breaking load;
  - `pictures.reply` (kid-facing) says a grown-up checks it again before anyone stands on it, and the turn isn't ok;
  - the history line reads "strength check: not resolved", because the study now records `unresolved` in the
    part's history;
  - the make card reads "not ready: a strength check isn't resolved".
- **The audit** (every reader of a strength run's verdict), each handling `unresolved`:
  - `answers`: both cards (#100);
  - `studies`: the load row (#100), the scorecard row and the release row (here);
  - `scorecard`, `release`, `kidbook` (here);
  - `chat._facts`: the raw numbers say "NOT RESOLVED…" (here);
  - `trials.predict`: the "Test it" prediction's basis says it's a rough guess (here);
  - the 3D callout, the history line, `pictures.reply`, `chat.picture`'s ok, the make card (#111 review);
  - not a strength-FEA verdict: the frame study and snow (beam models), goal labels, design-rule promotion;
  - `lighten` and `carve` stations: their own FEA runs, which this doesn't touch: #101 (CALI-106).
- Tests: `tests/test_unresolved_score.py` (main fails 4 of the first 6). `design.js?v=48`.
