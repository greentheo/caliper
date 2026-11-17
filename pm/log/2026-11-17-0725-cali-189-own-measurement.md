### 2026-11-17 · CALI-189 (#322) · "fixed (the X)" is the row's own measurement in the fresh run; main merged in

reviewer-2's re-check at 03a312a, and the foreman's one must-fix.

**The code was wrong.** `_moved` called a row fixed when no row of its own kind spoke for its failing case. But the list
makes a plate row only where the plate check governs. So on reviewer-2's real run, the step's plate read "fixed (the
plate)" while it was still under its need:
- step-stool-5 v12 at 500 lb;
- every panel thickened to 1 in;
- the step's plate at 1.91×, and the front rail's joints at 1.62× governing.

**Now**, before "fixed (the X)", `_own` reads the row's own measurement in each fresh case it spoke for:
- **plate:** that case's plate check for that panel, `safety_across`;
- **joint:** its row in `joints.rows`, by its pieces;
- **buckling:** that panel's entry;
- **a case's own row:** the case's safety.

The row is fixed only where each passes. One still failing is "still open", "measured: the top's plate is still 1.91×
where it needs 2×", with the safety as the card cuts it. One not measured there (a panel renamed, a joint not checked) is
"still open", "not measured as fixed".

**The small ask:** a joint is said by its own words, "the case still fails: the joint between the front rail and the
left side", not "…'s joint". A case's own row adds nothing after "the case still fails".

**Main merged in** twice, as merge commits: at 92efebd (through #326, clean) and again after #332 and #334 landed (two additive conflicts, both sides kept; no conflict markers).

**Tests** (test_fix_these.py). Each new one failed at 92efebd (the merge), run from a scratch tree:
- **the 500 lb shape:** one case, the plate at 1.91×, a joint at 1.62× governing. Still open, said;
- **the plate's panel renamed** (the seat holds): not measured as fixed;
- **the plate fixed while a joint fails its case:** the joint in its own words;
- **a joint the fresh run doesn't check,** another joint holding: not measured as fixed;
- **a panel that still buckles** while the plate governs: still open.

- **a plate row for two cases,** holding under one and failing under the other: still open, by its worst case.

**One test was wrong:** "a joint fixed while its case fails on the plate" had a fresh run with no joints in it. A real
run lists every joint it checks, holding ones too. It lists the joint at 2.4× now, and still reads fixed.

**Mutants (8), all caught in the end,** each run against test_fix_these.py and test_fix_list.py:
1. its own measurement never read
2. not found read as fixed
3. any panel's plate
4. the first joint listed
5. another panel's buckling
6. the plate along the grain
7. the best case, not the worst
8. a joint's words doubled

**Mutant 7 survived the first pass:** every pin had one case. The test was short. A plate row for two cases is pinned now
(reviewer-2's own run had two stepping cases).
