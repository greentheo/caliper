### 2026-11-12 · CALI-167 (#254) · An unsettled Lighten step doesn't lead "The step to use"

From #252's review. On the Lighten panel, a step whose re-check couldn't settle whether it holds (unseen or unknown, no
button) led "The step to use" before saying it couldn't be settled. That read as an offer the check doesn't support
(Rule 6). The lead now says what's known (`lightenLead`):
- "Not settled" for an unseen or unknown step;
- "Too little to use" for a step under the floor (#252);
- "The step to use" only where there's a button (room or no room), or for an older run with no offer recorded.

**Tests:** the lead test from #252 now pins all six cases. It failed on main for the two unsettled ones. Both mutants
(the branch dropped, and "unknown" left out) are caught. The floor and Use-it margin files pass (56).
