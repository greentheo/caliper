### 2026-11-12 · CALI-167 (#254) · An unsettled Lighten step doesn't lead "The step to use"

From #252's review. On the Lighten panel, a step whose re-check couldn't settle whether it holds (unseen or unknown, no
button) led "The step to use" before saying it couldn't be settled. That read as an offer the check doesn't support
(Rule 6). The lead now says what's known (`lightenLead`):
- "Not settled" for an unseen or unknown step;
- "Too little to use" for a step under the floor (#252);
- "The step to use" only where there's a button (room or no room), or for an older run with no offer recorded.

**Tests:** the lead test from #252 now pins all six cases. It failed on main for the two unsettled ones. Both mutants
(the branch dropped, and "unknown" left out) are caught. The floor and Use-it margin files pass (56).

**reviewer-2's must-fix, in this PR (the foreman's call): "Nothing lighter still holds" only where the steps were checked.**
On step-stool-2 (its solid filled in), steps 1–17 are untrusted and step 18 fails, and the panel said "Nothing lighter
still holds". That claims more than the check found (Rule 6, the red way).
- The line with no step to use is now `lightenNone`. Too coarse, unchecked or a span say so, as before.
- Any deeper step the check couldn't settle (untrusted, or no verdict) reads "Not settled: none of its steps could be
  checked, so no step can be said to hold."
- "Nothing lighter still holds" is said only where every deeper step was checked. A thinner sheet's estimate isn't a
  check.

Five shapes are pinned, step-stool-2's among them; both mutants are caught. `test_coarse_steps`'s panel extraction lists
the new function. The floor, Use-it margin, coarse-step and make-it-better files pass.
