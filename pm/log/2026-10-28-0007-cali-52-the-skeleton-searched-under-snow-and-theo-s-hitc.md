### 2026-10-28 · CALI-52 · The skeleton, searched under snow — and Theo's hitch call
- **Theo:** the hitch: 350 lb tongue weight (a Class III does 800); since the whole weight sits on the tongue,
  keep dynamic loads under ~3.5×; the lever-arm limit set aside — "worst case it bends the central spine,
  I may just have to test that"; 2x2x1/8 for spine, riser and tang; jacks at the back when parked, under
  350 lb with him in it. Snow: 20 lb/ft² ("1 lb/ft² per inch… a huge dump").
- **Frame v23:** 2x2x1/8 throughout — 25.8 lb of tube, 2.14× on a ×2.5 bump (yields at ~5.3× standing);
  gussets re-sized (v24): 0.69 kg / 5.9× / 90% off, 0.65 kg / 3.8× / 82% off. Flagged (scorecard note): a
  1/8 wall tang in the receiver bears ~1,300 lbf at the mouth on a bump — dents/ovaling; a 1/4 in wall or a
  sleeve for the 13 in shank is ~2 lb.
- **Skeleton (box v12):** front and back frames + roof beams as construction choices, `roof()` for the snow
  check, `snow.py` (panel/beam/rail checks) and `snow.search()` (exhaustive — 64 combinations in ~3 min).
  Lightest that holds 2×: **1x2 frames + two 2x2 beams across, no inside skin: 57.1 lb, $379, 2.01×** (box
  v13). Next up: three across, 59.2 lb, 2.7×. 2x2 frames unnecessary; an inside skin +9 lb/$117 for no gain.
- **Scorecard:** goals rewritten from Theo's words — tongue ≤ 350, frame survives 3.5× standing
  (`frame.yield_x`), walls/gussets ≥ 3.5× on a bump, snow ≥ 2×, every piece fits; the moment an objective.
  Notes on the card (the tang, fatigue). Result: 7 pass, 1 fail — walls 3.37× at the front wall's corner
  pieces (heavier box, more flexible frame); two layers of glass everywhere: +6 lb → 4.4×; a local patch
  would do it for < 1 lb (Caliper can't model a patch yet). 138.7 lb with 50 lb aboard, $439, 20% offcut.
- **Shape fingerprint** now ignores comments/layout; `shell`, `roof`, `BUILD_OPTIONS` not shape.
- Tests: `test_snow.py` (5). Full suite green.
- Commit: `787beac`
