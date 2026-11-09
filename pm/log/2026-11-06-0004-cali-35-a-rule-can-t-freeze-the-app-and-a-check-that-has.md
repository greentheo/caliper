### 2026-11-06 · CALI-35 (#103 review) · A rule can't freeze the app, and a check that hasn't run is never a pass
- **A rule Claude writes can't run away** (blocker 1: `9 ** 9 ** 8 > 0` ran over 60 s under OCCT on every design
  load). The plan's validator allows arithmetic, comparisons, and/or/not, the measures, names and numbers. It refuses
  `**`, strings, lists, subscripts, keywords, any attribute but a box's sizes and corners, rules over 300 characters,
  and a rule that doesn't answer yes or no (`rotor_d`, `1`). The evaluator refuses the same, as a second guard:
  powers above 4, a repeated string or list, ints past 256 bits, private attributes, and over 2,000 steps, each
  checked before it's done. So no rule can hold the lock.
- **`bbox()` has named corners** (`max_z` and the rest). The planner had been told `.max.z`, which a bounding box
  didn't have, so every such rule would have errored. Now it's tested on a real box against the skeleton.
- **A check that hasn't run is never a pass** (blocker 2, rule 6). `Report.said()` and `waiting` are used by the
  header badge ("1 pass · 5 not checked yet", never "all checks pass"), the chat ("No design check has run yet: 3 not
  checked yet.") and the card ("No check has run yet: 3 not checked yet.", warn). `all_pass` keeps its meaning,
  because the authoring loop stops on it and a part spec's deferred check (a print time with no slicer) must not hold
  it forever. Nothing a person reads uses it alone.
- **The planner's fallback reason is plain words** ("skeleton 1 unit is missing"), never pydantic's text and URL.
- Tests: the reviewer's runaway rules (the validator and the evaluator), the box rule, `said()` cases, the header
  badge (node), the card, and a "?" that's actually sent during review.
