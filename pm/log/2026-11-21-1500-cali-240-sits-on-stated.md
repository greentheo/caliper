### 2026-11-21 · CALI-240 (#1) · A sits-on rule is stated when the person's own sentence says it, and enforced

#1 slice D's end-to-end camper turned this up: the planner's "the box sits on the platform" rule came back assumed (shown, not enforced), though "a box on top" can be the person's own words. The foreman's call: when the person's sentence states the relation, the rule is stated and enforced; when the planner infers it, it stays assumed.

- **`plan.relations(said)`:** each "A on B" the person's own words say:
  - "A on top of B";
  - "A on B";
  - "A sits/rests on B" (and "that rests on");
  - "A atop B";
  - "B plus/and/with a A on top" (Theo's "a platform plus a box on top").
- **`classify`:** a sits-on rule (`bbox(a).min_z >= bbox(b).max_z - k`) is stated when a said relation names its a and b in that order. A name matches by its last word being one of the id's words ("the camper box": box). Any other rule, or a relation the other way round or to something else, stays as before.
- **The planner** is told the form a sits-on rule takes, beside its touch mate.

**Tests:** 13 in `test_sits_on_stated.py`, one per wording. 8 fail on main; 5 pin what stays assumed. All 7 hand-made mutants are caught. The plan (all four), plan-groups and first-run files pass, 187.

**Not here:** a group in such a rule needs #399 (rules over groups). The names are matched the same way once it's in.
