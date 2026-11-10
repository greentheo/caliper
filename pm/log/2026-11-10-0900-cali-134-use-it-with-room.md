### 2026-11-10 · CALI-134 (#167) · Use it offers a step with room to spare

**What was wrong.** Use it offered the deepest step that passed the study's own check, which has almost no room. The re-check on the rebuilt part reads lower, so it often left a part that doesn't hold.

**Measured** on five real parts at the default seven steps, real FEA, no Claude call. Re-checks read 0.67 to 0.89 of the study's number on steps with any room, and 0.49 on a step sitting at the goal. So the offered step must now clear what the part must hold by half again (1.5 times, which covers the 0.67). If no step does, it offers the one with the most room and says it may not hold. Deeper steps stay in the study.

| part | before: step, quote → re-check | after: step, quote → re-check |
|---|---|---|
| thick tube (carve) | 47% carved, 2.0 → **0.97, fails** | 35%, 3.05 → 2.72 |
| bridge (carve) | 35% carved, 2.6 → **1.95, fails** | 23%, 3.06 → 2.23 |
| tall ring (carve) | 35% carved, 2.27 → 2.01 | 12%, 3.86 → 2.60 |
| ring (carve) | 23% carved, 2.53 → 2.14 | 12%, 2.8 → 2.33, says it may not hold |
| step stool (Lighten) | step 8, 2.98 → 2.39 | step 7, 3.01 → 2.40 |

It costs material: the tall ring goes from 35% carved to 12%. Several re-checks are themselves flagged too thin for the voxels: the thick tube's, the bridge's and the tall ring's deepest. One run each, and the whole suite is CI's.
