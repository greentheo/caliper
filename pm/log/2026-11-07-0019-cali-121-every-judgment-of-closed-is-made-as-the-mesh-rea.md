### 2026-11-07 · CALI-121 (#133) · Every judgment of "closed" is made as the mesh reads back
- `measure.is_watertight`, `is_manifold`, `body_count`, `clean`'s own check, the weight's solid check and the
  whittle bridge go through `measure.closed()` (a merged copy, as any STL round trip): a pinch, watertight in memory,
  isn't closed for any of them. The bridge says where: "'box' isn't closed (near z …): whittle can't voxelize or
  carve it". A raw read is `closed()` itself or says why (`# raw:`), and a guard test holds every other line to it.
- **The build says once when its part isn't closed** (`chat._not_closed`, in the round's reply): "⚠ Its shape isn't
  closed near z … mm: strength, weight and carving can't be checked until it is."
- **#129's surviving mutant, pinned:** on a closed part the stray step drops a zero-area face anyway (it's a loose
  shell of its own); only on a part open elsewhere does the zero-area step alone take it out. The test is that case,
  and it's the one that fails with the step off.
- `tests/test_closed_everywhere.py` (5; 4 fail on main, the fifth pins the existing step).
