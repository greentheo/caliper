### 2026-11-11 · CALI-163 (#241) · An edit that names several parts changes each, and says which it didn't

Theo's step-stool-4 message ("make both sides the right side; the stretcher doesn't fit snug; neither slot is sized off the stretcher") went to side_left only, and the reply opened "✓ revised side_left → v2".

- **Routing by the request, not the selection.** An `Intent` carries `parts`, every part the change names, in the design's order.
  - Claude's router is asked for them ("both sides", "neither slot", "all the legs", "the stretcher and the left side"), and an unknown one is refused.
  - Offline, `named_parts` finds several only when the message says several: a word they share (both/neither/each/all, or a plural), or names joined by "and" or a comma. With a shared word, the parts named outright come too.
  - A part named only as a reference ("make the carriage clear the rail") still routes to one part, as before.
  - A selected part doesn't narrow a message that names several.
- **Each part is revised on its own, in order, built and checked before the next.** The designer is told which one this revision is for ("This revision is to side_left only: side_right and stretcher are revised on their own"). A revision that hands a part back as it was writes no version.
- **The reply says first what changed and what didn't.** For example: "! Changed side_left; side_right not changed: the revision left it as it was." "✗ Nothing changed" when none did. A ✓ only when every part named changed and nothing broke. A request to mirror says it can't be done yet (#239) and gets no tick.
- **"Still measures green" says what was measured:** "The design's checks pass (touch, no overlap); whether a part fits snug in its pocket isn't measured." That stays until #240's `fits_in`.

**Tests:** 15 in `test_several_parts.py`, all stubbed. Two existing tests pinned the old green line and are updated. 140 targeted routing and turn tests pass. Mutants wait until Theo's live session on 8011 is done.
