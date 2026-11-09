### 2026-06-12 · CALI-21 · Insert-into-assembly — the north-star headline, end to end
- **What it is:** *"insert a support between the wheel and the XYZ assembly."* The whole spine converges:
  CALI-20 (the posed existing parts + N-body measurement) + CALI-19 (fit bands) + CALI-16/17/22 (the
  author loop) → the LLM writes a part **in assembly/world coordinates** that mates to two named
  interfaces at a target fit, **verified by measurement**, then it's added back to the assembly.
- **`insert.py`:** `insert_spec(asm, between, fit, …)` builds a spec whose **references are the existing
  parts, posed** and whose assertions are the two fit **bands** + no-interference with every other part
  + one-body/watertight. `_bridge()` finds the separation axis + the two facing faces; the enriched
  intent hands the author the interface bboxes, the gap, and the facing-face coordinates in world space
  so it builds *in place* (not at the origin). `insert_part()` runs the author loop; `add_part_to_
  assembly()` appends the new part (run-dir source, identity placement) + two `fit` mates.
- **CLI** `caliper insert <asm> --between a,b --as id --intent "…" --fit slip --save out.yaml` (+ `make
  insert`): authors, persists the part (STL + `part.py`), adds it to the assembly, and **re-measures the
  whole assembly** with the new part in place.
- **VERIFIED LIVE (real Claude API):**
  - `insert` two-posts (50 mm gap) → the LLM authored a cross-bar **first try (1 round)**, landing
    **0.21 mm clearance to each post** (dead centre of the slip band 0.12–0.30); the script reasons from
    the interface bboxes, applies the clearance, and `.box(...)` in world coords. Assembly re-measured →
    ALL PASS (`crossbar_post_left`/`right` at 0.21, nothing collides). Saved assembly re-`assemble`s green.
  - Also confirmed the other LLM paths live: `gen` (authored a 4-hole part, 1 build-heal + 1 revision);
    `refine` of an authored part ("6 mm taller in z") — edited the real `part.py` (`bar_height = 10+6`)
    while keeping both fits at 0.21 (CALI-22 `refine_authored` seeding).
- Tests: `test_insert.py` (6) — bridge-axis, spec (posed refs + fit bands + no-collision + one-body),
  bad-interface guards, add-to-assembly mates, end-to-end author (injected) that mates both. **148 passed.**
- **Deferred:** webapp insert UI → CALI-21b; assembly parts built from a spec/intent at assemble time →
  CALI-23. Insert authors the geometry directly today; the multi-param optimizer (CALI-19b) isn't yet
  folded into the authored path (LLM revises dimensions instead).
  Commit: 7fb4d32
