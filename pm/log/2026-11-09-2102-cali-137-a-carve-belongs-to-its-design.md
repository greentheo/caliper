### 2026-11-09 · CALI-137 (#175) · A carve belongs to its design
Found reviewing #173: a carve on one design showed on, and could be cancelled from, another design with a part of the same
id, because the page kept its running carves by part id alone.
- The page's running carves are keyed by design and part (`carveKey`). A carve finishing after you've moved to another
  design updates nothing on the one on screen.
- Tests: tests/test_design_switch.py. Two mutants fail: the key without the design, and a late finish redrawing.
