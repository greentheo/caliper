### 2026-11-17 · CALI-207 (#345) · a check's cases, and a Lighten step's, solved on one solver: Lighten 83 s → 36 s, the same numbers

Theo asked for the Lighten speed-up. The foreman's (1), from my profile of one Lighten of step-stool-5 v7 at main (#298's comment): 44% of its 84 s was the multigrid hierarchy, rebuilt for every case of every step, and 7% making the solver.

**whittle first: `VoxelFEA.solve_each`** (greentheo/whittle#9, off 25e282e). It builds the set-up once and returns one result a case, bit for bit what a solver of that case alone gives:
- its own displacement, stress and peak (away from its own loads' attachments);
- its own deflection;
- whether it's supported.

whittle's `solve()` judges its cases together (worst stress, the first case's displacement), so it couldn't be used as it stands. That PR merges on Theo's word.

**Caliper:**
- **`load_study.solved(ctx, solid)`** makes one solver for every case of a check, each load at its own case, and calls `solve_each`.
- **Each case solved alone, as before,** where:
  - there's one case;
  - the whittle hasn't got `solve_each` (today's pin);
  - the cases held at once would pass `TOGETHER_MAX`.
- **`check_load(..., got=)`** takes its case already solved.
- **The strength check and Lighten's steps** call `solved` once a check and once a step.
- **Carve and pictures** aren't changed (not asked).

**The pin waits:** the Makefile's `WHITTLE_REF` moves to whittle#9's commit only once that's merged. Until then CI runs the alone path, and the bit-for-bit test skips.

**Identity** (scratch copies, deleted). Main (fb65a0f, whittle 25e282e) against this branch (whittle#9), each in its own process. Compared byte for byte on every case of each part:
- each case's displacement, von Mises, strain energy and solid;
- its supported, compliance, peak, deflection, converged and iterations;
- the strength check's whole record;
- one Lighten end to end.

| part | cases | identical |
|---|---|---|
| step-stool-5 v7 | 3 | all arrays, the record |
| step-stool-5 v12 | 3 | all arrays, the record |
| Theo's bar stool (i-want) | 1 | all arrays, the record |
| BOX_STOOL with a hole (test_lighten's `HOLE`) | 1 | all arrays, the record |
| Lighten of step-stool-5 v7 | 18 steps | the run's record, end to end |

**Time** (the same copies, the same runs):

| | main | this branch |
|---|---|---|
| Lighten, step-stool-5 v7 | 83.1 s | **36.0 s** |
| strength check, step-stool-5 v7 | 7.4 s | 3.9 s |
| strength check, step-stool-5 v12 | 7.3 s | 4.2 s |
| strength check, bar stool (one case) | 25.8 s | 25.0 s |
| BOX with a hole (one case) | 1.6 s | 1.5 s |

**Peak memory, three cases at once.** The bar stool has one case, so its seated load was given three strengths. That's a 118 × 118 × 148 node grid, 6.18 M node-cases. Each was run in a fresh process:
- together: **2,457 MB**, 11.1 s;
- one at a time, as main holds them: **2,330 MB**, 26.7 s.

That's +127 MB (5%). **`TOGETHER_MAX`** is 30 M node-cases, about 5× this part, so roughly +0.6 GB over one at a time on a 24 GB machine. Past it, the cases go one at a time.

**Tests** (tests/test_cases_together.py, 5 new). Each failed at fb65a0f, run from a scratch tree under both whittles:
- one solver, each load at its case, with its factor;
- alone with one case, with a whittle without `solve_each`, and past the bar (one node either side);
- the strength check solves once, and `check_load` never again;
- Lighten solves once a step, each case once;
- bit for bit against each case alone, on slice 1's stool. This one skips without `solve_each`, and passes with whittle#9.

**What my test was wrong about on the way:** Lighten's count only said `solved` was called, so a step that solved its cases again in `check_load` survived. It counts the per-case solves now.

**Mutants (9), all caught in the end,** each run against test_cases_together under both whittles:
1. every case alone
2. the bar inclusive the wrong way
3. the bar per case, not for all
4. every load at case 0
5. no factor together
6. check_load solves again
7. the study solves each alone
8. no whittle check
9. Lighten solves each alone *(survived the first pass: see above)*

**The full suite, under both whittles** (the pinned 25e282e and whittle#9's solve_each): one failure, the same in
each. test_resolved's stand-in for `check_load` didn't take the solve the study now hands it (`got=`). My test was out of
date, not the code; it takes `got` now, and the file runs green under both.

**Not this PR:** the coarsest level's factorization, 20 s of the 84, is a whittle change. It's noted on #298 and not queued.
