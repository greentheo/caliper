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
