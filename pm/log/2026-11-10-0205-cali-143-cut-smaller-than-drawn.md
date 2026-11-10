### 2026-11-10 · CALI-143 (#183) · A panel cut smaller than it's drawn is said

**What was wrong.** The stool's model has a 12 in round seat, and the piece it tells you to cut is 16-sided and 11.18 in across. On a part with a printed rest, whatever the pieces aren't goes to the rest, so nothing noticed the difference.

**The change.** `consistency.plan_differs` walks each flat sheet's outline, at mid-thickness, outward through the solid. If an edge has the solid running on more than 3 mm past it along its whole length, with no other piece to account for it, the card names the panel and gives both sizes. The stool's card says the seat top is 284 mm x 284 mm to cut and 304 mm x 304 mm in the model.

From the review: it's measured edge by edge, so a panel short at one end or in one direction is named. The size it gives for the model is where the solid really ends. The scorecard carries it as a warning, and the build book says it beside the cut list and in its header.

It's a warning, not a failed check: a panel set in a printed rim looks the same, and only the person knows which they meant. It only looks at parts with a printed rest, because anywhere else that solid is uncovered and the existing check says so. The samples show no alarms. The whole suite is CI's.
