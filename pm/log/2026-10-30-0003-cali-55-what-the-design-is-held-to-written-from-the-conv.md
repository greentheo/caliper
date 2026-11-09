### 2026-10-30 · CALI-55 (#2) · What the design is held to, written from the conversation
- **`goals.py`:** after the clarify round (in the background, off the request) and after any chat turn that
  sounds like a requirement (an obligation, a load, or a number with a unit), Claude rewrites the design's
  `scorecard.yaml` checks from its goal, requirements (answered or assumed), parts, the checks it has, a
  catalogue of metrics, and what was just said. Each check is **stated** (the person said it and the limit;
  their words kept), **assumed** (an assumed answer, or a number Caliper picked — the 2x behind "hold me"),
  or **proposed** (nobody said it, the design needs it; it doesn't bind until kept). A kept check stays kept;
  a dropped proposal is never offered again. Offline, "hold … 200 lb" still becomes a strength check. A
  goals file written by hand (the camper's) is never rewritten (`written_by: caliper` marks ours).
- **Live tuning (scratch stool):** the first prompt doubled the strength requirement (safety factor *and* a
  "stated" breaking load) and put "9 in off the floor" on the breaking-load metric. Rules now: one check per
  need, only what a listed metric measures, any number Caliper picked makes it assumed, short labels in the
  person's words; and in code, one check per metric and no unstated breaking load beside a safety factor.
  Result: "holds Dad (200 lb), 2 times over" (assumed), proposals "under $50" and "cuts fit on 1 sheet";
  then "keep the whole thing under $40 and light enough for him to carry" → "under $40" (stated) and "light
  enough for a 6-year-old to carry" (≤ 10 lb, assumed).
- **The scorecard** gains `strength.safety`, `strength.<part>.safety` and `strength.breaks_lb` from each part's
  strength check on its current version (run if missing); proposed checks show as ◇ and don't count. The
  panel shows where each check came from (*you said*, *assumed*, *kept*, *proposed* with **Keep**/**Drop**),
  before the first card too; the chat reply says what went on the scorecard and what it would also check.
- Tests: `test_goals.py` (5: offline strength check; a hand-written file left alone; Claude's stated,
  assumed and proposed checks, an unknown metric dropped, keep and drop and both standing after a redraft;
  a proposed check shown but not counted, the strength metric from the part's run; a requirement-ish turn
  updates the checks and a question doesn't). `test_scorecard.py`'s summary gains `proposed`.
- Commit: `e94ea70`, PR #36 (stacked on #35).
