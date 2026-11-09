### 2026-10-28 · CALI-46 wrap + CALI-47 · 2 in riser, and the scorecard
- **Theo:** go with the 2 in riser, then start the scorecard. Skeleton: posts where the shell is flat — a box
  inside the box — plus roof beams for a mild snow load, 1x1 ribs only if needed; "is there a way to do
  some sort of evolutionary optimization here?" (yes: CALI-52, the loop's first job). On the M6 spec: gates
  are user-specified constraints, colloquial, on the optimize side, and Caliper must find the crucial ones
  (the mattress) early; budgets default 10 min, user-set; cost **and waste** as objectives (the quadfecta);
  printed camper parts as the printer test case. Spec updated (§0, §5, §6, answers).
- **2 in riser:** frame v21 riser 2x2x3/16 (faces flush with shank and spine — no spacers): 30.2 lb of tube,
  3.56× (shank). Gussets re-sized at 1/8: jog_low 0.69 kg, 6.0×, 86% off; jog_high 0.65 kg, 3.8×, 80% off;
  v22. Frame 36.0 lb; design 133.5 lb, 3,108 lb·in standing. Cut plans refreshed.
- **Scorecard (CALI-47):** `scorecard.py`, `materials.PRICES` (rough; tube $1.90/lb, plate $1.50/lb, sheets
  whole), `frame_study.analyse`, `aero.drag_now`; goals in the design's `scorecard.yaml` (written for the
  camper from Theo's answers so far: payload 50, frame ≥ 3.3, walls ≥ 3.5, gussets ≥ 3.5, hitch ≤ 2,450
  *assumed*, every piece fits; objectives drag/weight/hitch/steel/cost/waste/sheets). First card: 6 pass, 1
  fail (hitch), drag 48.4 lbf, 134 lb, $446, offcut 23%. ~11 s.
- Tests: `test_scorecard.py` (4). Full suite green.
- Commit: `9fe2542`
