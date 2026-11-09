### 2026-11-07 · CALI-119 (#127) · A rule over the plan's own numbers is decided when it's planned; no rule sinks the plan
- **#117's live re-run:** the camper's planner wrote `tube_size * 25.4 <= 50.8` (the frame tube fits the 2 in
  receiver) twice; #117 refused a numbers-only rule, so the plan fell back to one part.
- **Decided at plan time** (`plan._by_the_numbers`): true, it's a note ("the frame tube fits the receiver (by the
  numbers: tube_size <= receiver)"), not a check; false, the plan contradicts itself and is refused with it, the
  numbers named ("tube_size * 25.4 <= 50.8 is false (tube_size 50.8 mm); lengths in a check read in mm", so the
  retry can see the slip); literals alone are left out, said.
- **No rule sinks the plan:** after the one retry a rule that still fails (an `=`, an unknown part, a contradiction)
  is left out with why ("I left out the check '…' (…): …" in the review, on the card); only a plan-level fault (no
  parts, a cycle, no answer) falls back to one part.
- **Units in `classify`:** speeds (mph, km/h, m/s) and masses (lb, kg) compare with what the person said, so "60 mph"
  is the planner's 26.82 m/s (or the "m" it wrote for a speed); skeleton units take m/s, km/h and mph.
- `tests/test_plan_numbers.py` (15; 14 fail on main), the camper's rule verbatim; #117's tests updated (a numbers-only
  rule is a note, a contradiction or left out; refused twice, the plan stands). design.js v=64.
- **#130 review:** deciding a rule uses the checks' own `approx` and `within`, and any error while deciding is that
  rule's fault (`PlanError(rule=…)`: retried, then left out and said), never the plan's. **A decided rule is plan
  data:** it stays in `rules` (never a check: `binding()` and the card's checks leave it out), its note is worked out
  on every validate, and what's left out is the plan's `left_out` field, so a revision shows both to the planner and
  "make the frame tube 3 in" is refused with "the frame tube fits the receiver, but tube_size <= receiver is false
  (tube_size 76.2 mm, …)", the plan as it was (a revision never drops a rule). A speed goes by its unit, never its
  name ("m" is a length). The card says "by the numbers" and a check's name once. Tests pin a note's whole path
  (the reply, the saved plan, the card, Keep) and the refused edit.
  Then: `left_out` is validate's own (a planner's answer can't claim a check was left out) plus, through an edit,
  the prior plan's; the "lengths in a check read in mm" hint goes to the planner's retry (`PlanError.hint`), never
  into what the person reads; both pinned.
