### 2026-09-18 · CALI-30 · Feedback becomes a test
- **The idea M4 is built on** (conversational spec §2): a chat tool that only ever *edits* accumulates
  drift — you say "make it clear the rail", it happens, and nothing stops revision #14 from quietly
  undoing it. Caliper has a better option than any chat-with-CAD toy because measurement is already its
  source of truth: **measurable feedback is promoted into an assertion**, and the existing evaluator
  enforces it forever. The history then splits cleanly — `history.jsonl` holds the narrative,
  `spec.assert` / `assembly.assertions` hold the enforceable residue.
- **Shipped — `src/caliper/promote.py`:** draft → **validate** → park → accept/decline.
  - **Two levels, because Caliper has two namespaces.** A rule about one part (`bbox.dz <= 40`,
    `min_wall >= 2`) lands in that part's `spec.assert` and is enforced by the author loop; a rule
    *between* parts (`min_clearance(carriage, rail) >= 2`) lands in `assembly.assertions` and is checked
    whenever **anything** in the design changes. Drafting picks the level; validation uses the matching
    context. The vocabularies are declared in the module so the prompt can't drift from what the
    evaluator actually binds.
  - **Validated before it is ever offered.** Every candidate is *actually evaluated* against the current
    geometry. An expression that won't parse, names a probe that doesn't exist, or throws is never shown.
    Offering a broken test is worse than offering none. `holds_now` is tracked separately from `ok` —
    a rule you don't satisfy yet is legitimate to state, but the chat must not imply you comply.
  - **Proposed, never silent.** The proposal is parked in `pending.json` and the **next turn** accepts or
    declines it. `turn()` short-circuits on a parked proposal, so "yes" confirms the test instead of
    being routed to *refine* and authoring a pointless revision (tested).
  - **Honest about the unmeasurable.** "Less chunky" gets no proposal. But feedback phrased as an
    **obligation** ("it must…", "never…") that *can't* be measured now says so out loud, rather than
    letting the user assume the rule stuck. Ordinary tweaks ("a bit wider") are left alone — offering to
    enshrine every edit is noise.
  - **Id collisions.** A promoted design-level id may not shadow a **mate** id: both expand into
    `derived_assertions`, and "what did this change break?" is keyed by id, so a duplicate makes the
    answer ambiguous. `_unique_id` steps aside.
- **Two things the LIVE run exposed, both fixed:**
  1. **A promoted design-level rule was enforced but invisible to the author.** `prompt_context` listed
     mates and part-level assertions, not `assembly.assertions` — so a revision could unknowingly violate
     a rule the human had deliberately locked in, and we'd only catch it after building. Now
     `prompt_context` includes design rules that mention the part (**DESIGN RULES IN FORCE**). Measurable
     effect: before the fix, "move it within 1mm of the rail" produced *no movement at all* (still 6mm);
     after, the author moved it to **4mm** — as close as the locked-in `>= 3` rule allows.
  2. **The reply glossed over a change that didn't do what was asked.** If the rule drafted from the
     feedback doesn't hold, that *is* the evidence the edit missed — so the offer now says so:
     *"it does not hold right now (measured 4) — so the change didn't actually achieve what you asked
     for."*
- **Conflict detection (added on the back of that run).** Asking for something that contradicts a rule
  you already locked in was silently producing a no-op. `promote.conflicts` reduces `left OP literal` to
  an interval and reports an empty intersection over the *same* measurement — deliberately narrow (bands,
  booleans and non-literals return "can't reason about it", because a false conflict claim is worse than
  none). The offer names the clash, and accepting **retires** the rule it replaces, logged in history.
- **Tests:** +51 (47 `tests/test_promote.py`, 2 `test_chat`, 1 `test_design`, +1 part-level enforcement).
  Drafting patterns, validation rejections, parking round-trip incl. a corrupt slot, accept/decline
  landing in the right file and surviving a reload, replace-don't-duplicate, mate-id collision, the
  LLM path held to the *same* validation, a failed drafter never losing the user's edit, and the two
  that matter most: **the accepted rule catches the regression on a later revision**, with a control
  test proving the same change sails through when declined. **265 passed.**
- **VERIFIED LIVE** (real Claude calls): *"the carriage must clear the rail by at least 3mm"* → revised,
  then offered `carriage_rail_clearance: min_clearance(carriage, rail) >= 3` (✓ holds now, measured 6) →
  *"yes, lock it in"* → promoted onto the design → *"it should sit within 1mm of the rail"* → the reply
  named the contradiction with the rule just locked in and offered to replace it.
- Commit: `1855322`

---
