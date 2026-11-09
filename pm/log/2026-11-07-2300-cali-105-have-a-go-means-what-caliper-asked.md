### 2026-11-07 · CALI-105 (#98) · "Have a go" means what Caliper asked; a part can be removed; a repeat asks first
From Theo's bar stool on 11/05: "have a go" after a rule that didn't hold authored a new part (`conical_skirt`); a
second cone would have had no way out; the foot flange widened by 1 in twice.
- **What Caliper asked, answered** (`caliper.awaiting`): a question Caliper asks parks what it waits for, as a
  proposal already does, and the next turn reads a short go-ahead ("have a go", "go ahead", "try it", "yes", "fix it")
  or a no against it first, with no LLM (`routed_by: pending`). After an accept whose rule doesn't hold, a go-ahead
  refines that part to meet that rule ("Change it so it meets its rule …: … Change only what that needs."). Anything
  else lets the question lapse. A longer message is its own request, never a yes.
- **Every instruction in Caliper's replies names its routing:** "Tell me to have a go" (the parked fix), "Say **roll it
  back**" (revert), 'say "put back …"' (restore); a test fails on a new one without a row.
- **Removing a part** (`caliper.trash`): "remove conical_skirt" / "delete …" / "get rid of …" asks once ("Remove
  conical_skirt? Its files go to the design's trash, so it can be put back."); yes moves its folder (script,
  versions, spec, history) to the design's `trash/` with what named it (its assembly entry, its mates and rules, its
  stated grain), takes it out of the design and `assembly.yaml`, and the design is measured again. "put back
  conical_skirt" restores all of it. A fixed reference (the car) goes the same way.
- **A repeated request asks first:** a refine whose words (or numbers and directions: "10 mm wider") match what the
  part's last revision just did asks "v2 already did that ("make the carriage 10 mm wider"). Do it again, on top of
  v2?"; yes does it.
- Tests: tests/test_have_a_go.py (11, stubbed: have a go after a failing accept, five ways, refines that part and never
  authors one; anything else lapses; every "Tell me to"/"say" routed; remove asks, removes, trashes, the cards drop it,
  put back restores it with its mate; no keeps it; a reference part; v2's instruction on v2 asks, not v3).
- **#153 review:** only a bare answer counts: the whole message has to be the go-ahead or the no (punctuation aside,
  "yes please" allowed). "yes, but make it taller", "no, make it wider" and "ok thanks" aren't answers: the question
  lapses and the message goes on as a request, so nothing is removed on a qualified yes. Removal covers the plan: the
  part, the plan's rules naming it and other parts' `mounts_on` come out of `design.plan` and back on restore, each
  where it was, or "Build it again" would author it anew. The reply names what went ("and its rule clear and mate
  carriage_misses_rail went with it"). `restore` never goes over a part of that name. With main's grain: what Caliper's
  waiting on is read first, and "cut the top with the grain" isn't an answer, so it still reaches the which-way
  question. Tests: 35; mutants (no plan, no rules, overwrite, an unanchored yes) each fail.
- **"Which way?" is parked too:** after "which way: front to back, or side to side?" for one sheet, a bare "front to
  back", "side to side", "along" or "across" states that piece's grain (read against the span the last check measured).
  One turn only; "front to back, and make it taller" isn't an answer, so it clears and goes on as a request.
- **Two parts in the trash, one put back (#153 re-check):** a mate or rule naming a part still in the trash waits in
  that part's entry and returns with it, and the reply says so ("The rule clear waits for carriage, which is still in
  the trash"): no check on a part that isn't there, nothing lost. The plan's rules and `mounts_on` do the same, in
  either order, and the plan keeps its original order while anything's out.
- **#153's one live run (Theo's OK):** routing was right, but the reply then offered to lock a looser copy of the rule it
  was fixing. A go-ahead to fix a rule no longer offers to promote anything (pinned: no proposal parked).
