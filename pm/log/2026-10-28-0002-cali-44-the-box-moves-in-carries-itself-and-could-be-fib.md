### 2026-10-28 · CALI-44 · The box moves in, carries itself, and could be fiberglass
- **Theo's calls:** drag design 2; X-only frame; 50 lb aboard; count the walls' strength and stiffness;
  fiberglass as an alternative to PMF; move the box close — the trunk is reached through the fold-down rear
  seat, so the hatch needn't open ("even just a few inches clearance").
- **Applied (design revisions):** cargo_box v7 = design 2 (wall_h 176, tumble 52, shoulder 1.4, nose 400/298,
  tail 662/159/228 mm); v8 = moved to `x_front` −3 in (3 in behind the bumper; was −18); v9 = `shell()`.
  frame v14 = follows the box, layout *X only, spine to the middle*; v15 = sized (below). Assembly: rule
  `hatch_clearance` retired, `bumper_clearance` (`min_clearance(cargo_box, leaf_rear) >= 2 in`) added — passes
  at 3.0 in; part `hatch_swing` removed from the design (files kept). Requirements recorded (no hatch access;
  ~50 lb aboard).
- **Moving in is the big lever:** box CoG 25.5 in behind the receiver mouth (was 41). With 50 lb aboard the
  receiver holds **3,428 lb·in standing** (152.8 lb) — vs 7,963 with 100 lb at 18 in. The shank no longer
  dominates at this size; the X's back arms do.
- **Drag at the new spot:** whittle scores the same (215 N vs 313 N plain) at 3 in or 18 in — its shelter is
  a silhouette, the gap isn't in the model. Real air usually rewards a smaller gap; not counted here.
- **Walls as structure (`shell()`):** 8 deep beams along the floor edges (front/back split where the
  shoulders curve in: 24 in deep at the ends, 41 in in the middle; sides ~39 in). Asked the whittle-agent for
  per-member material + Timoshenko shear — done within the hour (safety uses each member's strength; sweep
  leaves non-tube groups alone). Its advice taken: check the foam's shear on Caliper's side (cautious: all
  of it in the foam), mind skin wrinkling (glass on 1 in XPS wrinkles at ~42 MPa, well under its 200), local
  axes. Not taken yet: walls at mid-height with links (floor-line axis is the safe side).
  - Walls are strong: PMF skins ≥ 6.4–6.9×, foam ≥ 24×; one layer of glass ≥ 5.7× (wrinkling-limited).
    Stiff too: wall stiffness ×100 changes the frame by 3%; ×0.01 drops it to 1.4×.
  - **Counting them doesn't lighten the frame**: they carry the walls' and roof's weight to where the box is
    fastened — the X's four tips — which is where the X arms are weakest. As drawn 1.69× → 2.0×, sag 0.97 →
    0.71 in; lightest ≥ 3.5× (exhaustive over 4,700 tube combinations, not just the sweep's path): tubes-only
    46.0 lb, walls 47.7 lb (PMF) / 46.5 lb (glass). Fastening the front wall's middle to the riser top with a
    steel tab: 43.6 lb. The 2 in shank in the receiver (solid bar at 3.5×) sets the floor either way; a
    5/16 wall shank gives 3.3× at 36.8 lb.
  - Fixings: a corner fixing carries ~37 lbf on a bump.
- **Frame v15 (adopted, run station 6):** shank 2x2 solid, riser 2.5x2.5x⅛, spine 2.5x2.5x⅛, X 1.5x1.5x0.083;
  47.7 lb of tube + 3 lb gusset = 50.5 lb; 4.46× (x_back_right), sag 0.31 in on a bump.
- **Fiberglass:** one layer of 6 oz in epoxy weighs less than PMF (47.5 vs 52.3 lb box) and is ~15× stiffer
  and ~3.5× stronger as a skin (wrinkling-limited on 1 in XPS); two layers 53.7 lb. Box BUILD left at PMF
  (Theo's pick) — try it under **Built from**.
- **Glitch:** the server crashed twice on start (SIGSEGV, SIGABRT) while loading the design, with the full
  test suite and another session's whittle tests running; not reproducible after (sequential, threaded and
  real-server parallel requests all fine). Watch for it.
- **whittle sweep note:** with glass walls the sweep stopped at 3.45× ("nothing reaches 3.5×") though a
  heavier shank was in its list — the exhaustive search found 46.5 lb at 3.53×. Told the whittle-agent.
- Tests: `test_frame_study.py` +2, `test_construction.py` +1. Full suite green.
- Commit: `45ddc9f`
