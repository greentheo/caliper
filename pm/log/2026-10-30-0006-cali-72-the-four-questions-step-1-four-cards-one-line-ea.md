### 2026-10-30 · CALI-72 (#38) · The four questions, step 1: four cards, one line each, the numbers underneath
- Step 1 of `specs/caliper-four-questions-spec.md`. **`answers.py`** writes each card's lines on the server
  from what's already measured (no card runs a study to draw itself): *What is it?* (the description's first
  sentence, size, what it's cut from), *Will it work?* (each strength case as "Holds an adult stepping up, 3.1
  times over", "older version: check again", frames, rules; the scorecard for the whole design), *What do I
  buy?* (the shopping list in a line with its cost, the weight: "easy for a kid to carry" under 10 lb), *How
  do I make it?* (by tool from your shop, printed parts with hours, what your shop can't make grouped by why,
  patterns ready). A card with nothing yet says what to tell Caliper. Endpoint `/api/designs/{slug}/answers`.
- **The panel** is four cards, coloured by their worst line; "▸ the numbers" under each holds today's panels
  for that question (part: Size/Rules/History/Advanced; Will it hold?/frame/drag; Built from; Made in your
  shop/patterns/cut plan. Design: prompt/requirements/parts; scorecard/checks; weight & balance; build
  package), nothing removed, and stays open once opened (localStorage). A line from a study is a link to it;
  the Studies page opens the card a study lives in. Answers fill in place, so a half-filled form survives.
- **Glue and screws** join the shopping list (`fasteners.py`): joints found from the pieces (an edge against
  another's face or edge, each pair once), #8 screws a screw every 6 in (at least 2 a joint, ~1.6× the
  thickness long), glue ~1/2 ml an inch. The stool: 8 joints, 85 in, 18 × #8 × 1 1/4 in screws and an 8 oz
  bottle. In Built from, the scorecard's cost and the release's shopping list.
- Live, the stool's cards: "A two-step stool made from 3/4 in plywood…" (its description is stale until the
  next revision, #29's fix) · "16 × 10 in, 9 in tall, from 3/4 in softwood plywood" · ✓ "Holds 200 lb adult
  stepping up, 3.1 times over." · "1 sheet of 3/4 in softwood plywood, 18 screws and wood glue, exterior paint:
  about $39." · "It weighs 8.9 lb, easy for a kid to carry." · ✓ "With your jigsaw: 5 pieces." · "Patterns
  ready: 15 pages…". The cargo box and its frame read right too (the frame: "Your shop can't make shank,
  riser, spine and 4 more: steel tube…" until a welder and a saw are in the shop).
- Tests: `test_answers.py` (4: a five-panel box has 8 joints and its screws and glue; the four cards read top
  line first with no internal names; a strength check becomes a verdict and an older one says so; the design
  card says what isn't done). **Full suite: 496 passed.**
- Commit: `99ca894` (with the rest of CALI-48), PR #37.
