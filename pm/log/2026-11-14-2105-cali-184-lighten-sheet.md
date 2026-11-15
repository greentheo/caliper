### 2026-11-14 · CALI-184 (#295) · Lighten runs a plywood part with printed trim as plywood; Use sets the thickness; an unasked change in how it's made reads ⚠

Found on Theo's step-stool-5 v4: a plywood stool with a sliver of printed PLA, its inside corner fillet strips.
- **Why it went wrong:** `load_study.prepare` makes the FEA's base material the print whenever one piece is printed (it judges each voxel by its own material, which is right). Lighten read that `ctx["mat"]`.
- **What followed:** its holes' weight came out at PLA's 1.24 g/cm³ for plywood (0.56), and the top holes' allowable and plate check were PLA's. `run.material` was "PLA (printed)", so the thinner-sheet estimate's Use sent "Make it from 5/8 in pla (printed)", and the designer rebuilt the stool as one printed part (v5, read ✓).

- **1. Lighten's material is the sheet's.** `load_study.sheet_of(ctx)` is the plate check's sheet material, and the same as `mat` on a part with no sheet. Lighten reads it for:
  - its holes' weight and the thinner sheets' weight;
  - the holed top's allowable, in the study and in `judge_holed`;
  - the plate check at other thicknesses (`_plate_at`);
  - `run.material`.

  There's no `ctx["mat"]` left in lighten.py. The FEA keeps its per-voxel materials.
- **2. The check's headline names both.** A load-study record has `headline` ("softwood plywood, with PLA trim"; "PETG (printed), with softwood plywood pieces" for a mostly-printed part, as `made_of` reads it) and `plate_material`, the sheet.
  - **Where they show:** the page's "In …" line reads the headline. The plate check's thickness table reads `plate_material`, and so do trials (#209's sag across the grain).
- **3. An estimate's Use is a thickness, not a sentence.** Lighten and load-study records carry `sheet`: `{name, param, now}`.
  - **`param`:** the `PARAMS` number the script reads that equals the sheets' thickness (`sheet_param`; Theo's `ply_t`).
  - **Where there's one,** Use sets it through the Parameters route (`useParam`), with no designer and no material in words.
  - **Where there's none,** Use says "Make the 3/4 in softwood plywood 5/8 in".
  - **Both tables** (Lighten's estimates and the plate check's thicknesses) go through `sheetUse`. An older run's printed headline is never put into words.
- **4. A revise that changes how a part is made, unasked, says so and gets no ✓.** `refine_part` compares the construction's `(kind, material)` counts before and after. Where they changed and the request names no material or printing:
  - the first line reads "⚠ revised **panel** → v2 …: it also changed how it's made: 1 softwood plywood sheet became 1 PLA (printed) printed piece. Say "roll it back" to undo it.";
  - the turn isn't a success.
  - "Print it in PLA instead" isn't warned.
- **On a scratch copy of step-stool-5 set back to v4,** with this branch's code:
  - **The check:** headline "softwood plywood, with PLA trim", plate material softwood plywood, `sheet` `{softwood plywood, ply_t, 3/4 in}`.
  - **The Lighten:** `run.material` softwood plywood. Its last top step is **5.01 lb lighter** (it said 11.4 at PLA's density; the issue reckoned about 5.1 at plywood), and the 5/8 in estimate is **6.65 lb** (it said 14.7).
  - **The top's holes** run out at plywood's strength, at step 11 (1.56×), where PLA's had carried them further.
  - **The 5/8 in estimate's Use** sets `ply_t`, so nothing is put into words for the designer.

**Tests:** `tests/test_lighten_sheet.py`, 15 tests on synthetic parts (the #272 stool with a PLA strip, its thickness in PARAMS):
- a real Lighten's material, `sheet` and weights (the density worked back from an estimate is plywood's);
- the check's headline, plate material and `sheet`;
- `sheet_param`;
- `sheetUse` and `useParam` in Node;
- the ⚠ on an unasked sheet-to-printed revise, and none when asked.

All of them failed on main except the fixture's own and the asked case.
- **Mutants:** 15, all caught. Five survived the first pass, so there are three more tests: lighten never reads `ctx["mat"]` (it reaches the holed-top judge and the other thicknesses' plate check, which a test run doesn't); `sheet_param` takes one number the script reads, never two and never an unread one; and the param button's wiring.
- **Around run:** 125 files pass: every test that touches Lighten, the load study, trials, studies, verdicts, the card, the chat or the page, plus every guard that scans the source.
