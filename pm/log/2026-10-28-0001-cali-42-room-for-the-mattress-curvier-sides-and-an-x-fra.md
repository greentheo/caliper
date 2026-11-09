### 2026-10-28 · CALI-42 + CALI-43 · Room for the mattress, curvier sides, and an X frame that carries the box as built
- **Why:** Theo: widen the box so a twin fits inside the 1 in walls (~77 in) — now wider than the Leaf, the
  sides should be pulled in by the drag study, "keeping the mattress + 6 in width at the base"; then 1 in tube,
  and an X under the floor leaning on the plywood, with a gusset where it meets a 2 in beam in the middle.
- **Reading of "mattress + 6 in":** the bottom 6 in above the floor (a 6 in mattress) keeps the full width;
  above it the sides may come in. The mattress thickness is one number (`MATTRESS`) if he meant otherwise.
- **CALI-42 — the box (v6):** 77 × 40 × 41 in, floor flat and full size. One section function: full-width
  base to `wall_h`, then `tumble` (roof edges drawn in) + `shoulder` (straight → round, a superellipse), a
  rounded `nose_*` above the walls, a `tail_*` taper; a ruled loft of ~20 sections (0.01–0.7 s a build).
  `construction()` cuts the same surfaces into panels (flat end panels inside the shell, flat base strips,
  bent shoulder/roof shell; posts bevel-cut to meet the shell). 58.9 lb plain.
- **Reusable:** `keeps(params, build)` (boxes a part must hold clear) → `ParametricStudy.keep()` + Caliper's
  own surface sampler (`aero.keep_check`) on every station — whittle's KeepOut averaged over vertices, so a
  small cut-in passed its slack (told the whittle-agent; it now adds the deepest vertex). Report says whether
  each keep still fits with the BUILD tried; viewport draws it. `RANGES` = the part's own search ranges
  (unlisted numbers left unticked). Signature ignores RANGES/LAYOUTS, keeps keeps().
- **Drag study (8 numbers, behind leaf_rear, 65 mph, effort 0.6, 2,738 builds, 40 min):**
  start 313 N (the 74 in box was 293). Design 1: −4% volume, 16.8 lbf ≈ 3.3 kWh/100 mi saved; **design 2:
  −9%, 22.2 lbf ≈ 4.4**; design 3: −14%, 23.8 lbf ≈ 4.7. It wants the walls as low as the mattress allows
  (`wall_h` 170 mm, its limit), the **front rounded hard above the walls** (`nose_pinch` at its 300 mm limit
  over ~400 mm), modest tumble (2–4 in), slightly round shoulders (1.3–1.4), a long tail. Every design clear
  of the mattress. Lighter too: 54.0 / 52.3 / 50.9 lb vs 58.9. Not adopted — Theo picks.
- **CALI-43 — loads where they are:** `construction.load_points()` (each piece's weight spread over its
  area/length, ~100 mm apart; sums and balances exactly — 58.92 lb, CoG unchanged) + `design_loads()` (the
  design's parts + payload on top of the floor). `frame_study.study(from_design=True)` lands each on the
  nearest `"carries"` member as a point load (bins of 50 mm). First cut split members into 150 mm pieces —
  the whittle-agent caught that buckling would then be checked over 150 mm; it added `point()` and members
  stay whole (same numbers: bending governs). Layouts (`LAYOUTS`), a run picker, the hardest-worked
  **welded** joint (a tube running straight through doesn't count, unless a bigger tube is in the way).
  Frames weigh as cut (`from_members` joins straight runs, drops stubs); a frame's `construction()` now lists
  only its other pieces (the gusset), its tubes come from `members()`.
- **The X frame (v13):** 2 in spine (tops flush), 1 in X spine-middle → corners, 1 in front/back edges, 3/16
  gusset slotted round the spine; 48.4 lb as drawn (shank 16″, riser 8″, spine 50″, X 4 @ 42″, edges
  4 @ 37½″). Carrying box 58.9 + 100 lb payload, ×2.5 driving, target 3.5×:

  | layout | lightest at best safety | safety | sag | hitch standing |
  |---|---|---|---|---|
  | X only, spine to the middle | **64.7 lb** (X 2x2x0.083) | 2.38× | 0.69″ | 8,007 lb·in |
  | X + F/B edges, spine to back | 74.2 lb (X 1.5x1.5x0.083, edges 1x1x1/16) | 2.22× | 0.83″ | 8,592 |
  | X + F/B edges, spine to middle | 74.4 lb | 2.24× | 0.75″ | 8,524 |
  | X + all four edges | 79.1 lb | 2.17× | 0.87″ | 8,790 |
  | X + F/B edges, all 1 in | 78.9 lb (1x1x1/8) | 2.17× | 0.99″ | 8,784 |
  | X only, 1 in X | 54.1 lb — X arms fail | 1.33× | 1.38″ | 7,573 |

  **Every layout stops at the shank in the receiver** (2x2 solid bar, the biggest a 2 in receiver takes) —
  the load and how far back it sits, not the platform. X-only: 4.8× empty, 3.2× with 50 lb aboard, 2.4× with
  100. Joint at the X's middle ~2,700 lb·in per arm on a bump (gusset input, plate mode waits for Theo).
  The plywood + bonded foam walls stiffen the platform too; the study leaves them out (safe side).
- Tests: `test_aero.py` +5, `test_construction.py` +5, `test_frame_study.py` +4. Full suite green.
- Commit: `d9876cd`
