### 2026-10-27 · CALI-41 · What it's built from — weight, balance and a shopping list
- **Why:** the frame study showed the hitch carries ~6,400 lb·in standing still, dominated by weight far
  behind the pin. Theo's priorities: lighten the back (mostly foam, 1 in steel instead of 2 in), and get to a
  ~60 lb box: ⅜ in plywood floor, four 2x2 corner posts, 1 in foam + PMF everywhere else. He also wants this
  reusable, not tuned to this one project — and it's the groundwork for the cut plan and CNC DXFs.
- **Design:** a part declares `BUILD` (choices) and `construction()` (pieces), like a frame declares
  `members()`. Choices live apart from PARAMS on purpose: a drag study searches PARAMS, and a floor-thickness
  change must not make that study "stale" — `shape_signature` now ignores BUILD/construction/members/supports
  (no stored signatures existed yet, so normalising trailing whitespace was free).
- **The box (v5, shape unchanged — STL bounds identical):** floor full 74×39 in, walls standing on it, front
  and back full width, sides between, roof on top; posts in the corners inside the foam. Handles the tail
  shapes too (bent panels by facets) for when Theo picks one. **56.1 lb**: ⅜ ply 21.9, PMF 14.6, XPS 10.1,
  posts 5.4, hardware allowance 3.1, sealer 1.0. CoG 19.5 in behind its front, 14.2 in above its floor.
  Shopping list: 1 sheet ⅜ ply, 4 sheets 1 in XPS, 2 × 8 ft 2x2, 5.9 yd of 60 in canvas, ~0.8 gal glue,
  ~0.9 gal paint.
- **The design:** frame (2 in tube as drawn) **71.6 lb** at 34.9 in behind the receiver mouth + box 56.1 lb at
  40.5 in → **127.7 lb, 4,774 lb·in** standing. The frame is the bigger half — CALI-42's target.
- **Steel weight:** whittle's FrameStudy weighs with AISC's design wall (0.93× nominal) — right for stiffness,
  ~7% light for weight. Caliper weighs tubes at nominal wall with rounded corners (2x2x⅛ → 3.08 lb/ft vs a
  catalog's 3.05); whittle's 67.1 lb ÷ 0.93 ≈ 72 agrees.
- **UI:** part → **Built from**: weight, CoG, pickers for every BUILD entry (what-if, nothing saved), *Use
  these*, made-of table, *To buy*. Design → **Weight & balance** with a payload. Red dot = CoG, green = hitch.
  Verified in the browser (¼ in floor what-if → 48.9 lb, hitch 4,481 lb·in; reset).
- Tests: `test_construction.py` (18) + 3 API tests. Full suite green.
- Commit: `42f5fee`
