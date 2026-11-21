### 2026-11-21 · CALI-235 (#406) · A check that fails in the designer's round on a built part is a Things to fix row

Found by #1 slice D's end-to-end camper run (stub planner and designer, under `tests/`).
- A first build doesn't repair every round check (`build_plan.REPAIRS`), so a part can be written with one failing: a sheet off its face, or (with #404) a wall beam off its wall, or the mattress cut by a wall.
- The What is it? card said it. Things to fix didn't list it: the camper's two seeded box faults came back with an empty list. That's against Theo's rule: every red flows into Things to fix, with a one-tick fix and a re-check.

- **`fixes._round_rows`:** each check `consistency.checked` failed on the part as built is a row, `check:<id>`, measured.
  - **A construction check:** said as the card says it ("Its 3D shape and its pieces don't match: …"), with the card's own fix (`answers.fix_for`'s first words).
  - **#404's two:** their own fix (`ROUND_FIX`). An id at the start of a check's words stays as it's written.
  - **Not a second row:** none where a strength run's row already speaks for the check (`filled` for the volume and cover checks). The bare-edge warning is the edge row's, not a fail.
- **After Fix these:** it reads Fixed when the check passes on the new version.

**Tests:** 7 in `test_round_checks_to_fix.py` (a stubbed `consistency.checked`, a stub designer, no live call). 4 fail on main; the other 3 pin a true part, a warning and a pass as no row. All 6 hand-made mutants are caught:
1. round checks not listed;
2. a warning listed;
3. a pass listed;
4. no own fix;
5. the construction words not the card's;
6. said twice beside a run's row.

The 37 files that read Things to fix or Fix these pass, 269. In the end-to-end camper (local, with #404), the two seeded box faults come back as rows, and each fix reads Fixed.
