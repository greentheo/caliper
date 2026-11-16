### 2026-11-16 · CALI-189 (#318) · #318 review: every failing case gets a row; the list is this design's; a number names all it moves; no failing number rounded up

reviewer-2's review of #318 at 8b6211d. The foreman accepted four must-fixes under Rule 6. All four are fixed here, with the three small asks.

**1. Every failing case gets a row.** On v7 at 500 lb the step fails at 1.07×, and no stock sheet in its table clears it. The list said "Nothing measured wrong with it" under a ✗.
- A plate fail with no stock answer now says so: "…; no stock sheet clears it: the thickest, 1 in, is 1.91×". It comes with the designer's choices: hold it up underneath, brace it, or ask it to hold less.
- A buckling wall with no stock answer gets the same, using the same stock.
- Any other failing case (the FEA's) gets "It doesn't hold X: 1.3× where it needs 2×; it works hardest in the front rail", with designer choices.
- Every failing case is now covered by a row, so "Nothing measured wrong" only shows when nothing fails.

**2. The list is this design's.**
- On the page, `S.fixes` and `S.fixMine` are keyed by design and part (`fixKey`). They're cleared when another design opens, and `fresh()` checks the key and the version.
- A row's ticks and rewording are keyed by its id and its measured words (`fixRowKey`). A new number is a new row, so they don't carry over.
- A list that comes back after another design has opened is dropped.

**3. A number names everything it moves.** reviewer-2's v7 at 350 lb: `ply_t` sets all six panels, and the row said only the step. Where the run's `sheet.pieces` puts other pieces on the same parameter, the fix reads "Make every panel 1 in (ply_t sets the step and the other five)", or names the pieces where it's a subset. Its cost says what it moves, and the choice carries `moves`. The piece alone is offered beside it as the designer's choice.

**4. No failing number is rounded up.** The list prints safeties cut toward safe (`V.cut`): 1.96 reads 1.96×, not "about 2.0×".

**Small asks:**
- "measured" sits on the problem line, and each fix says "proposed". A reworded row still shows neither: it's the person's words.
- Both thickness fixes use the plate check's own stock table, to 1 in. Theo's v2 wall at 0.69× now says no stock sheet clears it (1 in is 1.63×), not 1 1/2 in.
- A buckling row from a push in the wall's own plane adds the card's racking line to Known limits.

**Tests:** 13 of the 14 new or changed tests failed on 8b6211d. The 14th, an unmeasured finding, pins a filter that was already right, and closes reviewer-2's survivor. The t³ test uses 0.9×, where t² would need 28 mm and t³ needs 1 in. That closes the other survivor.

**Fault calls:** the code was wrong on all four must-fixes. No test was wrong.

**Mutants:** 17 of 17 caught: the four old ones that matched code the rework moved, re-aimed, and thirteen new ones. These include reviewer-2's two survivors (t² for t³, and an unmeasured finding kept).
