### 2026-06-11 · 🎉 M0 COMPLETE · CALI-2/4/8 verified end-to-end with real geometry
- Verified the OCCT-dependent path. Fixed a generator bug: the CadQuery `"XZ"` plane normal is
  `(0,-1,0)`, so `extrude` is sign-defined and left the body off-centre on Y (bolt holes landed at
  the flange edge). Now recentre from the actual bounding box.
- **CALI-4** generator confirmed: corner bracket builds watertight, one body, 4×Ø5.2 holes on the
  bolt circle, optional Ø10 cable bore.
- **CALI-2** B-rep hole detection + `holes_matching(on=circle(60), count=4)` confirmed.
- **CALI-8** `caliper run "...four M5 holes and a cable pass-through" --no-llm --yes` → draft spec →
  clarify gate → loop → **ALL PASS** (bbox [60,20,60], min_wall 2.99, 4×Ø5.2 ✓, mass 8.1 g,
  watertight 1 body, bore Ø10) → 128 KB `runs/run_0000/part.stl`.
- **Full suite: 47 passed.** Verified in a pip CadQuery scratch venv (numpy-2 alias shim for the
  abandoned `nptyping`) because the conda env was still solving; re-confirmed later in the conda env.
- Commit: `ff8e154`.
