### 2026-10-28 · CALI-46 (part) + M6 spec · Tube end cuts, foam bevels, and the make loop
- **Theo:** proceed; and the bigger question — design, optimization and manufacture as one iterative
  cycle, his shop (CNC plasma, CNC router, small 3D printer, a big printer later) as constraints, him in the
  loop only to verify stages. Answered with a plan and wrote it up as `specs/caliper-make-loop-spec.md` (M6:
  scorecard → the shop → moves → loop runner → build package; three gates: requirements + shop, trade-offs,
  release to cut; never silent about relaxing a requirement). Board: M6 cards CALI-47…51.
- **Tube end cuts:** `cutplan.tube_cuts()` from members(): setbacks to the face butted, mitres from the
  angle, corners closed by the bigger tube. Checked by hand on Theo's frame (X arms 42.04 in centreline −
  1 in ÷ sin 63.1° = 40.92 in, mitre 26.9°).
- **Bevels:** the driver groups unfold-to-sheets' seams by the pair of pieces and reports length and the
  angle they meet at; the cut list bevels each edge at half (≥ 2°). Seen: the shoulder is nearly vertical
  with tumble 52 mm over 865 mm, so the bands are near-coplanar in the middle (0–3°) and the top band meets
  the roof at a corner — the strip-built split is mostly for the nose and tail.
- **Plate mode:** forwarded Theo's go-ahead (his words: "okay great, yes, let's do proceed") to the
  whittle-agent with the joint loads; it's building `frame.gusset(...)` on whittle `plate-mode` (its PRs #1,
  #2 — the frame-study work — are merged to whittle main). Its flag: the 2 in shank and 2.5 in riser
  faces are ¼ in apart — a cheek plate needs a spacer, or a 2 in riser.
- Fixes: score-line count counts only what's drawn; cut-plan notes only for the materials present.
- Tests: `test_cutplan.py` +1. Full suite green.
- Commit: `005321a`
