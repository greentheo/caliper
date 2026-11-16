### 2026-11-16 · CALI-185 (#312) · #312 fourth round: an open question and a case turned off reach the strength line the scorecard shows

reviewer-2's check at 7070e3e: round three's fixes held. One must-fix was left, and the foreman adopted it.

**The must-fix.** The open question about a part's loads, and the cases turned off, went only on the per-part metric `strength.<part>.safety`, and nothing displays that. The design-wide strength line the page shows never had them. So a pass at the more demanding value read as a plain ✓ "model".
- Each part's off list and open questions now go into the design-wide `strength.safety` metric's note. Each part is named where there's more than one.
- Every strength check gets them too: as `loads`, which the page draws under the line, and in its `note`.
- An open question gives the line a trust label of its own, **question open**: on the per-part metric, on `strength.safety`, and on the check when it's a pass or a fail. "not resolved" still means too coarse to see its walls, and it still wins over the question.
- Pinned on the check the page shows: the open question (its trust and words, against a control with none), the off list, and the page's line.

**#314's rule flips Theo's step-stool-3.** reviewer-2's correction: on step-stool-3, the two-sided top's free edges are its sides (x ±152 mm), and the only load on one was its script's "tipping sideways". With tipping cases no longer counted as feet, its own unedited loads now read "middle only": "the top is held on two sides, and no load stands on its free edge…".
- That's CALI-94's rule as written, NEEDS ENGINEER CHECK.
- step-stool-3 fails on its joints under #311 anyway, so its card stays ✗ and gains the warning.
- The fix on Theo's side is a strength case at a side edge. reviewer-2 checked that adding one clears the warning. Theo should hear this with #311's values.

**Small asks, done:**
- **An untouched Save writes nothing:** no version, no history, every check still current. That holds with or without an override.
- **`_demand` is pinned** with a mixed-unit pair (yours 150 kg against the design's 300 lb: yours) and a margin pair (yours 260 lb ×2 against 300 lb ×1.5: yours).
- **The guard closes the realistic gaps:**
  - a `ctx`, `p` or `run` bound from a `.declared(` call is no longer allowed;
  - a bare `unchecked(` call is caught;
  - `"loads_edge"` anywhere in a comparison is caught (`in ("loads_edge",)`).

  It also reads only loads: a store into `c["loads"]` isn't a read. The variable-key form is left, as reviewer-2 said.

**Fault calls:** the code was wrong for the must-fix and the untouched save. In my new tests I was wrong twice:
- a check without a `metric` key;
- the page's `esc` leaves apostrophes alone.

**Mutants:** 10 of 10 caught. One ("the check's trust left plain") survived first, and it was the test's gap. A plain pass or fail takes its trust from the metric, which already says it. The check's own override matters where the line's trust would otherwise be its joints note, and it's now pinned with a verdict resting on unchecked joints: the question's label wins, and the joints stay said.
