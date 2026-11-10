### 2026-11-09 · CALI-100 (#92, the page) · Make it better on the card, as Theo's mockup has it
Theo approved the mockup: *"looks great, love the layout."* Stacked on the server side (#157).
- **On *Will it work?*:** a "Make it better" heading, each offer as what to do, a muted line with what it costs, and a
  button (`better.offers` now gives `lead`, `cost`, `button`, `part`; `text` is the same as one sentence). They're not
  drawn as verdict lines.
- **Each button goes through what its panel already does:** "Try it" says it in the chat, "Check it holds", "Carve it" and
  "Lighten it" start them, "Use it" takes the step and checks it again. On a one-part design's card it selects the part first.
- **Walls too thin for the check:** the first offer is what would let the check see them ("Make the cone skirt walls
  9.2 mm so the check can see them"), from the wall the check can see at this size (`sees_mm` on a new run; an older
  run has it in its words). No filament number: nothing measures it yet, and the mockup's was a placeholder.
- **Carve shown disabled with why,** where the check can't be trusted yet ("It waits for a check it can trust"). Before
  any check the only line is "Check it holds first", with a button that runs it. A part that fails as drawn is still
  only offered what would make it hold.
- Tests: tests/test_make_it_better.py (+11: the wall offer from a new run and an old one, Carve disabled, each offer's
  shape, the card's section run in node, each button's route). In the browser on a copy of the stool with its check
  set to the mockup's state: it matches, Carve is disabled, no console or server errors.
- **#159 review (reviewer-2 ran the real check, not the edited record):**
  - The wall offer stops promising. A real 9.2 mm wall came back still too thin, because the thin spot on the stool isn't the wall `wall_t` sets. Where the thin spot is a point (a real run's `{"at": …}`) it now says where and what to do; "make it N" is only for a named piece, rounded up, and it says a finer check follows and what that costs.
  - Theo's stool reaches the screen: a fail on a run too coarse to see its walls gets the thin-spot line and Carve off with why. A fail on a settled run is as it was.
  - Carve and Lighten runs are in `answersKey()`, so a finished run updates the card and a stale "Carve it" can't start a second carve.
  - "Use it" quotes say they're the study's own check and that using it re-checks.
  - `runLoad` and `runLighten` take one click; "Try it" with no key says Claude isn't set up here.
- **#159, second round:** the point line says a finer check is what it takes, with its cost. A tab left open re-reads the state before starting a carve or Lighten, so it can't start a second one. One number for the wall on one screen (rounded up, `load_study.sees_from`). A carved part's own sliver points at rolling back, not "thicken it". Use it takes one click, Carve it is off while its carve runs, and the no-key message has no "Report it…".
