### 2026-11-16 · CALI-189 (#322) · "fixed" is the cases passing; rules by their own id

reviewer-2's must-fixes 2 and 3 from the first review, as the foreman accepted them.

**2. "Fixed" means the cases passed.** Row ids are piece and case names, so a revise that only renamed the step to the
top took its row off the list, and the row read "fixed".
- Each row the strength check makes now carries the cases it speaks for (`cases`) and what it's of, in words (`what`).
  A joint failing in two cases is one row speaking for both.
- A check-made row gone from the list is **fixed** only where every case it spoke for passes in the fresh check (by
  case name, through `verdicts.meets`), or where no row in the new list speaks for any of them.
- Otherwise it's **still open**: "it's measured as 'the seat' now".

**3. Rules by their own id.** Rule rows were `rule:{i}`, by position: with A and B failing, B ticked and A fixed, B
became `rule:0` and `rule:1` read "fixed". They're `rule:{id}` now (the rule's own id, else its expression).

Tests: 5 new:
- the rename, reworded and by its own choice;
- rules A and B;
- a passing case read as fixed though a joint row speaks of it;
- a joint's row naming both its cases.

The rename and rule tests failed on the old source. 8 mutants, all killed. One survived until the rename test also ran
a fix picked from the row's own choices: a chosen fix had lost its cases.
