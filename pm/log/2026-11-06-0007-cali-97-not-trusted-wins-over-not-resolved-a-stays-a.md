### 2026-11-06 · CALI-97 (#100, merged with main after #96) · "Not trusted" wins over "not resolved"; a ✗ stays a ✗
- **Merged `main` (with #96) into #100.** Where both reword one strength verdict:
  - the filled-in shape's "not trusted" comes first, because the check ran on a block, the more basic problem;
  - "not resolved" or "not checked" comes next;
  - a fail stays a ✗ under both.
- **A filled-in part that fails** now reads ✗ on the part card, the design card and the Studies row, with "It ran on a
  filled-in shape, so the part as built is weaker still". The block is stronger than the hollow part, so a fail on it
  is certain. #96 alone had read every filled-in verdict as a warn.
- **Page:** "not trusted" first, then "not resolved", then holds or doesn't. `design.js?v=45`.
- Tests: `test_filled_verdict` (both together on the design card and in Studies).


---
