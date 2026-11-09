### 2026-11-06 · CALI-94 (#106 review) · A ✓ from the middle foot only isn't one
- **The reviewer's block:** a two-sided top loaded only in the middle read a green ✓ on *Will it work?* ("Holds a kid
  stepping up, 2.2 times over", `MIXED` at 60 lb), when with the front-edge foot the same stool reads ✗ 1.91×. The
  warning was only on *What is it?*.
- **Now, while `loads_edge` names a bare top** (`consistency.bare_edge`, cached per version and script like
  `filled()`), that part's strength ✓ is a warn: "Holds a kid stepping up in the middle: checked in the middle only;
  the front edge, where people stand, isn't checked (add a "stepping on the front edge" case)". It reads that way:
  - on both cards;
  - in the scorecard, as status `edge` (summary `edge`, never a pass, so the release isn't ready);
  - in the book's header and *Will it hold?* row;
  - in the Studies rows;
  - in the kid's book, which makes no promise.
- **Round 2 of the review, the readers that still said "holds":**
  - the strength panel's badges, the run's header and its picker read "middle only";
  - the stress callout reads "middle only: the middle read 2.2x; the front edge, where people stand, isn't
    checked", with no breaking load;
  - the history line reads "strength check: checked in the middle only" (the study records `middle_only`);
  - the picture reply says a grown-up checks it before anyone stands on it, and the turn isn't ok;
  - `chat._facts` says "CHECKED IN THE MIDDLE ONLY… no verdict".
  - The page asks one helper, `caveat(c)`, for any ✓ that isn't one ("not resolved", "not checked", "middle only"),
    and the design state marks each case `middle_only`: ready to fold into the one verdict function the foreman is
    filing. The make card's `edge` branch waits for #111's `_why_not` to reach `main`. `design.js?v=51`.
- **A ✗ stays a ✗.** The authoring round still only warns, as #73 scoped it.
- Tests: the reviewer's case, the same stool with its edge foot (✗ 1.91×), and the printed-sides warning path (`under`).
