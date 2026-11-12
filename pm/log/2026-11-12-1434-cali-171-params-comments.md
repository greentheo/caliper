### 2026-11-12 · CALI-171 (#266) · A rewritten number's comment says the new number

The first part of #266, Theo's live step-stool-5. After his Parameters edits, step_stool's script read `"height": 406.4,
# 20 in`, `"width": 406.4,  # 24 in` and `"top_depth": 355.6,  # 11 in`. The designer read the comments, and the new
fillet part copied a 20 in stool.

`aero.write_params` rewrote the number by its source position and kept the comment as it was. Every rewrite goes through
it: a Parameters edit, the skeleton's drive, and an adopted drag or frame study. Now it also restates the comment
(`_restate`):
- **A length figure that is the old number becomes the new one, in the comment's own unit.** Inches are said as the page
  says them: to the 32nd as a fraction, else three places. So "# 20 in" → "# 16 in", "# 3/4 in plywood" → "# 1/2 in
  plywood", and "(101.6 mm)" → "(152.4 mm)".
- **Any other figure stays:** "3/4 in plywood, 1 1/4 in screws" changes only the 3/4.
- **A comment already stale from an earlier edit**, whose one figure is no number it had, says the new number. This
  applies only where the number's name says it's a length (Theo's `"width": 406.4,  # 24 in`). "4 in a row" on a count
  stays.
- An angle's or a count's comment is untouched, and so is every other line.

**Tests:** 14 in `test_params.py`. 11 failed before; the other 3 pin what's left alone. Theo's shape of PARAMS is a
synthetic copy, not his script. All 8 mutants are caught; one survived at first (a mixed number misread) and now has a
case. The 15 test files that rewrite PARAMS or drive the skeleton pass, 488 (params, aero, mirrors, skeleton drives,
the plan and build-plan files, shared sizes, release and the rest).

Next in #266: a part added to fit another reads its live numbers, the pick's coordinates become a requirement, "and the
opposite edge" makes a mirror, a seating check runs before the reply, and the findings run after an added part.

**Rework from reviewer-2's review (the foreman's must-fix).** The fallback for an already-stale comment rewrote a lone
figure that was another thing's size: "fits a 3/8 in bolt" became "2 1/2 in bolt", and "3/4 in ply sits in it" became
"1 1/4 in ply".
- **A lone figure is stale only where it states the number:** first in the comment (a "~" may lead), then nothing, a
  comma or bracket, or a size word (tall, wide, deep, long, high, thick). Theo's "# 20 in", "# 24 in, side to side" and
  "# 11 in deep" are still put right. The bolt, the ply and "deep enough for a 10 in foot" stay.
- **"1-1/4" is one mixed number.** As this number, it's said as "1-1/2", hyphen kept. Otherwise it stays whole; it was
  "1-1 1/2".
- **The Parameters label drops the comma after the figure** (reviewer-2's small ask): ", side to side" is "Side to side".

**Not done:** the other small ask, putting Theo's other stale comments right without an edit (width "24 in", top_depth
"11 in", rails "3 in", foot_overhang "2 in"). They're put right as each number is edited. A pass over a whole script
when it's opened is left for #266's live-numbers part. That part changes what the designer reads anyway.

**Tests:** 9 more in `test_params.py` and 3 label cases. The 5 review cases failed before. All 5 mutants are caught.
`test_params` passes, 124, and `test_aero` and `test_mirrors` pass, 80.
