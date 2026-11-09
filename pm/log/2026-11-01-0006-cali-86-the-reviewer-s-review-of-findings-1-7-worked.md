### 2026-11-01 · CALI-86 (#62), #69 rework · The reviewer's review of findings 1–7, worked
The foreman accepted every disagreement in the reviewer's review of #69. One commit per item, new commits only
(the reviewed ones keep their hashes).
1. **(rule 6)** The beam now takes where the foot is. Near a free end the width is no more than half the
   effective width plus the foot's distance from the end (BS 8110; NEEDS ENGINEER CHECK, with the DIN Heft 240
   note): 190 mm, not 280, for a foot at the end of a 900 mm panel. The tests go through `plate_check`.
   Centred loads are unchanged. `13460bd`
2. The report scrubs anyone's home folder. A 500 says a plain sentence and the error id. A YAML error keeps
   its line and column, never the excerpt (the reviewer's "a surprise stool for Emma"). Failed jobs go the same
   way. The dialog now says what's true. `fe3c39e`
3. Trial steps, the log and part histories are read defensively. A bad line is left out and counted, never a
   500, and the API takes `true` as no number. `d37c422`
4. A sample is saved beside the old one and swapped in, so a failed save leaves it whole. `1e42dfe`
5. The pattern tests cover the front and back panels (the x-only mutant fails them). Titles print without an
   em dash (a test renders each character). `9c6765b`
6. The carve line names which part holds. The headline reads the step it names, and when carving makes the
   whole part fail, the headline says so and isn't green. `02bd3d8`
7. **(rule 6)** In the kids' book, the kid stands an arm's length behind and never in front of the saw, with
   ear defenders. The wood is clamped with the line past the table's edge. The grown-up stands on the new stool
   first. `95369a3`

---
