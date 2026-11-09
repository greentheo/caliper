### 2026-10-27 · CALI-39 (follow-up) · The first real design, and what it taught the PARAMS contract
- **Theo's answers:** receiver ~9 in off the ground and 3 in forward of the bumper; ~51 in from there to the
  roof (60 in); teardrop/hatchback rear; Class II hitch; the hatch swings at most ~14 in behind the bumper.
  Built his design in the real UI, driving the shared browser pane: `a-cargo-box-on-the-trailer` — a Leaf
  rear stand-in (hatchback profile, a guess to correct), a `hatch_swing` envelope (both references), the
  2 in tube frame, and the box (tunable: tail params at 0). Clarify answered 3, assumed 2 (rear door,
  6 in roof fan — the rear door conflicts with tapering the tail; flagged to Theo). The box request's
  "must clear the hatch swing by at least 2 in" became `min_clearance(cargo_box, hatch_swing) >= 50.8`,
  validated (4 in today) and locked in.
- **Found live — the author put PARAMS *inside* `build()` and wrote `70.5 * 25.4`**, violating both halves
  of the convention, so the reader saw nothing. Fixed both sides: `read_params` also finds PARAMS at the
  top of `build()` and folds arithmetic on numbers (rewrite replaces the whole expression span, comment
  kept); the prompt now says *first statement, outside build(), finished numbers, inches in a comment* with
  an example. The next three parts all came back in the right shape.
- **The loop doing its job:** the frame came back with its ladder running 9 in forward under the car; two
  chat corrections (scoped to the frame) fixed it, measured each time (v3: ladder exactly -57..-18 in). A
  box request I sent while the frame was still selected was — correctly — treated as a frame change; it
  failed to build in 4 rounds and **the frame was left untouched** (never write a part that won't build).
- **Engineering flags raised with Theo:** Class II usually means a 1¼ in receiver (frame shank must match);
  the box's centre sits ~40 in behind the receiver — the empty box + frame (~110 lb est.) already puts ~3,800
  in·lb there vs ~2,000–2,500 for a typical Class II rating; departure angle ~8° at a 12 in floor.
- Tests: +2 (`test_aero`). 77 passed across aero/chat/API.
- Commit: `990fe80`

---
