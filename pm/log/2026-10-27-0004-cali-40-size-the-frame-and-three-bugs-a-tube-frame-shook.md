### 2026-10-27 · CALI-40 · Size the frame — and three bugs a tube frame shook out
- **Why:** with the camper shell shaped, Theo turned to the 2 in steel underframe: "how can we whittle that
  part down to use as little steel tube as possible", plus gussets at the riser's 90-90 jog for his CNC plasma.
  Voxels can't see a 1/8 in wall at 74 in, so the tube frame is a *frame* problem. Coordinated with the
  whittle-agent session: it built `FrameStudy` (beam solver, tube catalog within 1% of AISC HSS, sweep from as
  drawn to lightest-that-passes) on its `frame-study` branch; plate mode for the gussets comes after, fed by
  the frame's end forces at the jog. Theo's calls: frame first; no legs yet (driving case only).
- **Shipped — `src/caliper/frame_study.py`:** a part declares its own structure — `members(params)`
  (centrelines, tube, group, and the PARAMS that size it) and `supports(params)` — read in a separate process.
  Ends within 1 mm merge into joints; tubes map to whittle's catalog keys; two cases: `standing` (x1, the
  number to compare with the hitch rating) and `driving` (x2.5). The sweep's chosen tubes are written back
  into PARAMS as a parametric revision. API `/api/designs/{slug}/frame-study*`; the inspector shows **Size the
  frame** (not drag shaping) for any part with members()+supports(); previews fade the other parts.
- **Result on Theo's frame (100 lb on the rails, x2.5 driving):** as drawn (2x2, 1/4 shank) 67 lb of steel,
  weakest **1.45x** (riser, driving), sags 1.24 in. **The hitch holds 167 lb and 6,394 lb-in standing still**
  (15,984 at x2.5) vs ~2,450 lb-in for a typical Class II (350 lb x ~7 in). The sweep lightens the ladder first
  (1x1 rails, 2x2x0.083 cross members: -22 lb, *safer*), then puts steel at the jog (3x3 riser and upper shank,
  2x2 solid in the receiver): **3.32x at 63 lb** — it cannot reach 3.5x with what fits a 2 in receiver. The hitch
  moment barely moves with tube sizes (5.5–6.4k lb-in): it's the 100 lb box 40 in out. Matches the agent's run.
- **Three bugs the tube frame exposed, all fixed:**
  1. **Author replies were capped at 2,000 tokens** — a seven-tube frame + members() came back cut off
     mid-line, every attempt, as a baffling SyntaxError. Cap now 8,000, and a cut-off reply fails the build
     with the real reason ("write it more compactly").
  2. **`body_count` counted air as bodies.** Where a hollow tube's open end sits inside another tube, its bore
     is a sealed pocket whose surface is a separate mesh shell — a welded frame read as 6 "bodies", which also
     derailed the LLM's last attempts. Now counts B-rep solids when present, else only outward-facing shells.
  3. **The LLM author kept misplacing tubes** (corner-anchored boxes: cross members at y -93..-30 in). After
     three rounds I wrote the frame script myself — hollow tubes hollowed individually then fused with overlaps,
     members() whose ends meet at the joints (13 members, 12 joints), supports() for the receiver socket.
- **UI:** the run picker / stale-study guard for drag studies (`043a9cb`), a back link from an accidental "+ New
  design" (`1b37143`), and previews now fade other parts (the box hid the frame).
- **The Caliper server was SIGKILLed once** (exit 137, no traceback, RSS ~0.5 GB before and after) — external,
  most likely macOS memory pressure; not reproduced.
- **Tests:** +14 (`test_frame_study` 9, `test_measure` 3, `test_authoring` 2). 62 passed across the touched files.
- Commit: `117960e`

---
