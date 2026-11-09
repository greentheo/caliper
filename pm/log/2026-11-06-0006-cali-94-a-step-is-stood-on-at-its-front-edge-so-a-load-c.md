### 2026-11-06 · CALI-94 (#73) · A step is stood on at its front edge, so a load case puts a foot there
- **The designer is told** (`part_scripts.md`): a top or tread resting on only two sides gets a second load,
  "stepping on the front edge", the same foot mid-span with its edge on the free edge, listed first. A top held all
  round keeps its one centred foot.
- **The designer's check warns** (`consistency`, `loads_edge`): when a top held on two opposite edges has no load
  within half an inch of a free edge, it says so. It's a warning, not a fail: the round passes, and the part card
  shows it (warn). `load_study.two_sided` finds the sheet a downward load lands on, and whether it's held on two
  opposite edges; for a top on printed sides, the solid under it counts as holding, as the plate check reads it.
- **The suite's two-sided fixtures get the case** (the test stool's `LOADS`, `MIXED`). Before and after, at 2 voxels
  through, both governed by the plate check (a beam across the two held edges):

  | Fixture | Middle foot | Front-edge foot | The part, before → after |
  |---|---|---|---|
  | Test stool (3/4 in top on two sides) | 1.46× | **1.19×** | 1.46× → **1.19×** (✗ either way) |
  | `MIXED` (1/2 in top on printed sides) | 0.66× | **0.57×** | 0.66× → **0.57×** (✗ either way) |

  The FEA agrees the edge is worse (4.76× against 10.38×, and 2.19× against 3.41×).
- **The sample stool doesn't get the case:** it's a box, its top held on all four sides (no warning). By the issue's
  own rule it keeps its one centred foot. **The one number asked for:** on the sample and `BOX_STOOL`, a front-edge
  foot reads 3.11× like the middle one (the plate check's formula is for a centred load; it doesn't move), and the
  FEA reads the edge no worse (11.3× against 11.2×; 19.1× against 16.2×).
- NEEDS ENGINEER CHECK: BS 8110 cl. 3.5.2.2's edge width, as read; and the plate check's centred formula for a foot
  near an edge of a panel held all round.
- Tests: `tests/test_edge_foot.py` (main fails 4 of the 6), `test_load_study`, `test_mixed`. Two carve tests changed
  with the fixture: the carve that "dies at the second step" counts a check per load, and the carve-down test uses
  `MIXED`'s middle foot only (`CENTRED`). With the front-edge foot, the carve picks a step whose adopted part isn't
  watertight, at 40 lb and at 50 lb alike; that's a carve-adopt defect of its own, #105.
