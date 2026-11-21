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

**Rework from reviewer-3's review (the foreman's three calls):**
1. **Every word of a part's id must be named** (plural allowed). "a box on top of the deck" no longer states `box_lid` on `deck_leg`, `tool_box` on `deck` or `box` on `deck_frame`; "the tool box on top of the deck" states `tool_box`.
2. **No bare "on".** Only wordings that say up and down: "on top of", "atop", "sits/rests on", "sits/rests on top of" (the commonest phrasing), and "B plus/and/with a A on top". "The logo on the box", "a shelf on the wall", "paint on the box", "hinges on the lid" and "a box on the deck" stay assumed.
3. **One sentence or line at a time.** "a camper with a lid", answered "on top of the truck bed", doesn't state lid-on-truck_bed.
- **And:** a negation ends a phrase by rule ("isn't on top of", "never on top of"). The plus-form needs plus, and or with ("the truck has a box on top" stays assumed). "it" names no part.

17 more tests and 2 changed: "a box on the deck" is now assumed, and the "on it" case is pinned as "on top of it". 12 fail at 02b9b65. All 8 rework mutants are caught, including the reviewer's two survivors. The plan (all five), plan-groups, first-run and build-plan files pass, 227.

**Re-check (reviewer-3, the foreman's two one-line fixes):**
1. **The phrase's last word is the id's last word too** (singulars of "-s" and "-es" read). "a box lid on top of the deck" states `box_lid` on `deck`, not `box`. "two boxes on top of the deck" states `box`.
2. **A phrase a negation stops says nothing:** "no box sits on the deck", "there's no box on top of the deck", "not a box …", "without a box atop …" stay assumed. An article between them doesn't hide it.

6 more tests; 5 fail at 9d68a9c. All 4 mutants are caught.
