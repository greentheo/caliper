### 2026-10-30 · CALI-73 (#39), CALI-74 (#40) · Lighter until the safety runs out; the four questions, steps 2–4
- **Theo:** "it seems that we've hit an artificial limit… still 3.1X safe even though we removed 3.3 pounds,
  shouldn't we take this chart down as far as I can go until the safety factor runs out?" Right: the study only
  took the walls (to one window each inside the 1.5 in glued rim), and the 3.1x is the *top's* plate check, which
  it wasn't allowed to touch.
- **Lighten, three phases (`lighten.py`):** the walls as before; then round 1 1/2 in hole-saw holes in the panel
  stood on, one at a time, quietest first; then thinner sheet as estimates (from the lightest step with the top
  solid: the plate check at that thickness, the walls' FEA scaled), adopted through the chat. It stops at the
  first step that doesn't hold (shown red). Stool: walls to 49% (3.27 lb, 3.11x) → 1–4 holes near the top's
  corners (3.29–3.37 lb, 3.09–2.98x) → a 5th, nearer the foot: **1.69x, fails** → in 5/8 in: **4.15 lb lighter,
  2.16x (estimate)** → 1/2 in: 1.38x, fails. The top works nearly everywhere; its holes save 0.02 lb each.
- **How a holed top is judged:** the plate formula ignores holes. Tried and dropped: the FEA's maximum (one corner
  hole: 3.1 → 1.8x, the stair-stepped edge of an 8-voxel circle) and its 99th percentile (still 3.1 → 2.4x). Kept:
  the rest of the panel by the FEA with a ring round each hole left out, and each hole's edge by K_t = 2 (a round
  hole in a plate in bending, Peterson) times the stress the solid panel had there; both scaled by how far the
  FEA read low against the plate check on the solid panel, recalibrated after each walls step (the top's holes go
  into the windowed part). **A bug the tests caught:** after adopting top holes, the strength check judged the top
  by the plate formula again — 3.1x for a top the study put at 2.1x. Now `judge_holed()` does it the calibrated way
  for any top that has holes (solving once with them filled, cached). The study's number and the rebuilt part's
  can still differ (stool, step 8: 2.98x here, 2.38x rebuilt — the hole edges fall differently on the grid), so
  cutting a step in reruns the strength check, and the panel says that's the number to go by.
- **Step 2:** *Will it work?* lists the design's checks (`scorecard.yaml`): a verdict from what's measured now
  (`answers.measured()`: strength runs on current versions, weight, cost, what the shop can't make, print hours),
  else the last scorecard (said so when a part has changed since), else what it needs; proposals to keep or drop.
  A design with requirements and no checks gets them written once in the background — the stool now has
  "holds Dad (200 lb), 2 times over" (assumed: the 2x is Caliper's) and reads "✓ … 3.11x"; the cargo box's nine
  hand-written checks read from its scorecard (✓ tongue 141.3 lb … ✓ floor 3.3×). The design's *What do I buy?*
  reads the measured weight and cost. `JobRunner.busy()` keeps the backfill from queueing twice.
- **Step 3:** *How do I make it?* has its own buttons: Print full size, Measure and mark, Project; Open the build
  book. **Step 4:** clicking a card's title drives the viewport: *Will it work?* the stress, *What do I buy?* and
  *How do I make it?* the pieces as built, *What is it?* the part.
- Tests: `test_lighten.py` (it goes down until it runs out: walls before the top, the top judged by the plate check
  solid and the calibrated FEA holed, estimates never adopted as they stand, hole-saw holes round; adopting and
  rechecking agree within 15%), `test_answers.py` (+1: what it's held to — not checked yet, ✓, ✗, proposed; a lone
  part answers for the design). **Full suite: 497 passed.**
- Commit: `7b8b097`, PR into #37's branch.
