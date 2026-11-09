### 2026-10-28 · CALI-46 (part 2) · Gusset plates — whittle plate mode, into the design and the cut plan
- **whittle-agent shipped plate mode** (whittle `plate-mode`, uncommitted): `frame.gusset(node, m1, m2,
  thickness, plates)` → `PlateStudy.sweep()` → stations whose `.design` is a `Cut` (outline + holes, `.dxf()`
  R12 mm with `$INSUNITS 4`, `.svg()`), metrics (mass, safety, stress, sag, holes) and — asked for — how much
  of the corner weld's moment the plates take (`plate_share`, `weld_moment_nmm`, a sentence in `.note`).
  Reach now runs the member's full length; notes say when to cut one plate over both corners, and the ¼ in
  spacer the 2 / 2.5 in faces need.
- **Caliper:** `GUSSETS` in the frame script names the joints; `frame_study.gussets()` builds the frame
  carrying the design as built (walls, 50 lb), runs each joint, files every station's DXF/SVG under
  `designs/<slug>/gussets/<id>/`, picks the lightest that keeps 3.5×; `adopt_gussets()` writes `PLATES`
  (data — not shape, so drag studies still apply); the frame's `construction()` weighs them; the cut plan
  draws them via whittle's `Cut`. API `/api/designs/{slug}/gussets*`; page: *Gusset plates* under Size the
  frame. Fixed on the way: a support with `fix: "all"` was split into letters by `build_spec`.
- **Theo's frame:** 3/16 plates: 1.02 / 1.09 kg each, 5.7× / 7.3×. 1/8 plates: **0.74 kg, 6.5×, 84% off the
  riser/shank weld** and **0.71 kg, 4.3×, 82% off the riser/spine weld** — adopted (frame v20). The X's middle
  plate dropped (v18). Frame 36.2 lb (29.8 tube + 6.4 plate); design 133.7 lb, **3,109 lb·in** standing.
- Open for Theo: the ¼ in spacer (shank and spine faces sit ¼ in inside the riser's) or a 2 in riser.
- Tests: `test_frame_study.py` +1 (skips without plate mode). Full suite green.
- Commit: `6e64f16`
