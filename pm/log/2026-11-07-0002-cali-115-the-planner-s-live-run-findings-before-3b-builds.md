### 2026-11-07 · CALI-115 (#117) · The planner's live-run findings, before #3b builds on plans
- **Fixed only for what you have:** a `fixed` part whose words say it's made (welded, printed, cut, plasma-cut, to
  build…) is refused with that reason, and so is any fixed part when nothing the person said says they have something.
- **No part for the ground, the floor or the room:** validation drops it, with the mates and rules that name it
  (`plan.dropped`). **One part to build builds at once:** `P.buildable` counts parts to make, so a reference part
  doesn't stop the first run for review. The stool's step says "one part (the bathroom floor is what it stands on,
  not a part)".
- **One retry:** a refused plan goes back to the planner once with the reason, then falls back to one part. `=` in a
  rule says "`=` isn't a comparison; use `==`".
- **No tautologies:** a rule that calls no measure of a part and names no part ("shaft_d == 25.4") is refused.
- **Invented numbers are proposals:** `classify()` marks a skeleton number `stated` only when the person gave it (any
  unit: "1 in" is the planner's 25.4 mm), and a rule `stated` only when it reads stated numbers. Everything else is
  `assumed`, whatever the planner wrote, and not enforced: only `binding()` rules go into assembly.yaml. Review shows
  "assumed: not checked until you keep it" with **Keep** (`POST …/plan/checks/{id}/keep`). A revision doesn't undo
  a keep. design.js v=54.
- `tests/test_plan_live.py` (31; all fail on main). One #103 test now expects only the turbine's stated rule enforced.
- **Not done here:** the accept's live re-run of the three sentences. It spends Theo's key, so it needs his word in
  night shift's session (a relayed word doesn't count).
- **#123 review:** what it stands on is dropped only when its id's last word is a ground word and it isn't made
  (`floor_lamp`, `wall_shelf`, `ground_stake` stay; `bathroom_floor`, `garage_wall` go), and it's always said
  (the review reply, the card, the one-part step). Making is read from `made` only ("a Honda generator, built in
  2019" is still yours). A fixed part with no possession phrase near its own noun is **assumed**, "(you have it? say
  if not)", not a refused plan; "my kid's science fair" isn't having a generator. Keep marks its numbers kept (tested).
