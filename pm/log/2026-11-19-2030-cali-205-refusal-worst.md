### 2026-11-19 · CALI-205 (#339) · the refusal names the worst failing case, and so does every line that names one

Found in caliper-reviewer's review of #338. `load_study.already_fails` (Carve's and Lighten's refusal) names the
lowest case. A mutant that took the first failing case survived every test. Since #338 the refusal's words depend on
that case: its number, and where it fails.

**Pinned:** a part with two failing cases, in either order:
- a foot on the step, failing by the floor's plate check at 1.6;
- a hand on the top, failing at a joint at 0.9.

The refusal reads "it already fails (0.9 times over, at the joint between the front rail and the left side)", never the
plate check. That passed on main too: the refusal was right, just unpinned.

**The check the issue asked for found a red.** A ✗ line that names one case should name the one the refusal names, and
two didn't:
- the design's line for a coarse fail (`answers.measured`'s `strength.coarse_fail`);
- the scorecard's (`_compute`'s `hedged`).

Both took the *first* coarse fail. On a coarse run with two FEA fails, the back at 0.8 then the front at 0.4, the
refusal said "0.4 times over, … in the front", and the design's line said "Its worst stress … is in the back".

**The fix:** `answers.worst_failed`, the lowest of several failing cases, as the refusal picks it. Both lines use it.
`test_newest_run`'s pin on `measured`'s source line moves with it.

**Fail first:** the coarse line (back first), the helper and the scorecard guard failed on main. The refusal's pins
passed, as above.

**Mutants** (each anchor once, scratch copy), all 5 caught:
1. the refusal takes the first failing case (the issue's);
2. `worst_failed` takes the first;
3. `worst_failed` takes the highest;
4. `measured` takes the first;
5. the scorecard takes the first.

The scorecard's is pinned by a guard on its source; its `_compute` runs a whole scorecard.
