### 2026-11-16 · CALI-189 (#318) · Things to fix after #311, #313 and #312: a joint's own row, and the edited loads' rows

#311, #313 and #312 merged. Main is merged into #318 (no conflicts), and the list now reads what they added, as the foreman asked.

- **A joint that gives first** (#301, a hand check's row with `holds` false) is its own row: "The joint between front rail and the left side gives under a foot: 1.4× where it needs 2× (two #8 screws pulled out of the front rail's edge)".
  - It covers its failing case, so there's no "doesn't hold" row beside it.
  - Its fix goes by how it gives:
    - a pull: held another way, by screws through a face, a pin, a wedge or a glue block (nothing in an edge holds a pull);
    - shear: more screws or a glue block;
    - bearing: a thicker piece or a cleat;
    - a notch's net section: a shallower notch or a wider piece.
  - "Ask it to hold less" sits beside it.
- **What the hand check couldn't do is a known limit, never a row:**
  - a joint it couldn't place ("Not checked by hand: …");
  - a load path it couldn't follow;
  - racking under a sideways case (#313's words).
- **The edited loads (#312):**
  - an open question gets a row with its own words ("You'd edited … ; the design now asks …: checked at the design's 300 lb until you choose"), and the choices **Take the design's** or **Keep mine**;
  - a case turned off gets a row ("'X' is turned off, so nothing checks it"), with **Turn it back on**.

  These are a new kind, `loads` ("a change to its loads, at once"), carrying the scenario's case and what to take. Slice B applies them through the scenarios route.
- **Tests:** 3 new, all failed first without the rows. 29 pass in all.
- **Mutants:** 8 of 8 caught.

**reviewer-2's re-check (#318 at 16d760a, with main), adopted by the foreman: the list reads #311's joint verdicts as the card does.**
- **A joint that fails is its own row, in the card's words:** "The joint between the side back and the stretcher gives first under stepping on the front edge: three #8 screws pulled out of the stretcher's edge; under 0.1× where it needs 2×".
  - "Gives first" is the governing joint's alone; another that fails "gives too".
  - Its fixes are the joint's, all designer edits: the way it holds (screws through a face, a pin or a wedge for a pull; more screws for shear; more bearing), a glue block, or a different joint.
- **Every number is the card's own** (`answers.safety_num`): 1.07 against 2 reads "1", a tiny one "under 0.1", never "0×".
- **"Its joints aren't checked" only where #311 didn't reach,** read per case (`verdicts.wood_brace(run, c)`) in the card's words (`joint_said`):
  - the joints it couldn't place, by name;
  - a path it couldn't follow;
  - an old run's "the check takes its 10 joints as solid wood".
- **"It works hardest in…" only where the FEA judges the case.**
- **A row of a case under an open question says which value it's of:** "…; of the design's 300 lb, pending your choice" (or "of yours, 260 lb").
- **Small asks:**
  - "every panel" is judged against every sheet the part declares, so a box with more panels names the ones the number moves;
  - tiny numbers in the card's words.
- **Probed on this merged tree** (scratch copies of Theo's step-stool-3 and step-stool-5 v7, each freshly checked):
  - step-stool-3 fails on its joints, under 0.1×. Its rows are the two stretcher joints ("gives first"), the top's joint to the side front at 1.3× ("gives too"), and the bare front edge (#314's flip). There's no "works hardest", and no joints limit: #311 places them all.
  - v7 holds at 2.15×, with every joint checked by hand: no rows, no limits.
- **Tests:** 34; the 9 new or changed failed on the round before. **Mutants:** 7 of 7 caught.
- **Around run** (81 files, on the merged tree): one failure, and it was the code's. The verdicts guard (`test_no_module_works_a_verdict_out_for_itself`) caught `fixes.py` reading a joint row's `holds` for itself. It now asks `verdicts.meets(safety, need)`, as Make it better does. After the fix: the guard and the list's tests, 71, pass.
