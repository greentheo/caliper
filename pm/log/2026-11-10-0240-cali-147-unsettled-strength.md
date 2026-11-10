### 2026-11-10 · CALI-147 (#191) · The scorecard says when a strength number isn't settled

**What was wrong.** On a run too coarse to see its walls, the card and `blocked` hedged, and the scorecard didn't: `strength_loads` read `fail` at 0.53x with an empty note, and `strength.breaks_lb` read 200 lb.

**The change.** A ✗ stays a ✗, as it does on the card. On a run that can't see its walls, the check carries "not resolved: too coarse to see its walls" as its trust and the card's own hedge as its note, with no margin. `strength.safety` says the same. `strength.breaks_lb` has no value and says why, and one part's unsettled run means no smallest load from the others. The build book's row reads "about 0.53x, not settled: too coarse to see its walls" with no breaking load, and its header counts the fails that aren't settled. A resolved run reads as it did. `SCORER` is bumped, because a card's breaking load can change.
