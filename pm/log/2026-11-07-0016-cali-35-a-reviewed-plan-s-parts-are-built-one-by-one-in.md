### 2026-11-07 · CALI-35 (#3b) · A reviewed plan's parts are built one by one, in order
- **Build it on a reviewed plan** (`build_plan.build`, from `firstrun`): each part to be made is authored in the plan's
  build order, mounted-on first, narrated ("Building the mast", "The mast: built (mast_height ✓, …)"). A part the
  person has (`fixed`) isn't designed. "The plan's saved … comes next (#3b)" is gone.
- **Each designer sees the skeleton and what's built** (`DesignStore._plan_context`, in `prompt_context` when there's
  a plan): every skeleton number in mm with its unit and why, each part already built with its world bounding box,
  and the plan's checks between parts.
- **A rule between parts fails the round:** `authoring.improve` takes `interfaces`, the plan's mates and rules over this
  part and the parts already built, measured each round with the skeleton's values (`evaluate_assembly`); a rule
  over a part not built yet waits. A failing one is fed back like any failing measurement.
- **A part that won't build** stops the run there: the parts before it stay, the reply names it and why ("Build it
  again to retry it, change the plan, or carry on without it"), and Build it again carries on from it.
- **#103's review items:** a revision's history says `waiting` (amber "not all checked", with `said`) when a check
  couldn't run, never a green "passed"; the chat says "The whole design measures green" only when every check ran
  (`chat._design_line`), else `Report.said()`; each evaluator guard is pinned on its own (the string repeat too).
- `tests/test_build_plan.py` (10, stub authors that build boxes from the skeleton): every interface holds; a mast
  100 mm short fails its round naming `mast_height` and the retry fixes it; the designers' prompts carry the skeleton
  and the built parts' boxes; a part that won't build stops there and Build it again goes on; the history and chat
  lines; the four guards. #3a's "comes next" test now checks Build it starts at the base. The skeleton driving the
  parts (rebuilds on a change) is #3c.
- **#135 review:** a part's line has a mark only for what was measured on it (none, no mark; a check waiting, `·`);
  the reply gives the design checks in `said()`'s words and says what isn't checked yet ("whether it holds (Check
  it holds) and the scorecard. Run *Will it work?* next"), and `ok` stays False while a rule waits; a rule over a
  part the person has says "needs the generator's size: say it, or keep it off", and the designer's prompt names
  that part (YOURS, not designed); the plan's review says the cost before Build it ("3 parts to make, up to 4
  designer tries each (at most 12)"), which a run can't exceed; the stop gives the reason's last line, the traceback
  goes to the log; a history line fails only with a failure (all waiting is waiting). Tests pin the assumed mark in
  the prompt, `ok` with a waiting rule, and a rule over a part not built yet.
- **Merged with main's one verdict (#132):** the revision history's `result` is `verdicts.report`'s kind (main's
  `_result`; #135's own copy goes), and the build's marks come from verdicts: each rule's from `verdicts.check` (a rule
  that waits reads "·", an error "✗"), the part's from `verdicts.report`, and the build's `ok` from its
  `counts_as_pass`, not `all_pass`.
- **#135 review, round 3:** the marks are `_marks(mine)` (what `build()` uses, tested with erroring and failing rules,
  not a copy of it), and a design whose measurement throws (`_measure_design`'s `(None, {"<design>": …})`) says "The
  design checks: not checked: …" and isn't ok: it read `report is None` as ok (rule 6).
