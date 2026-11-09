### 2026-09-18 · CALI-29 · The chat turn handler — and the verb that didn't exist
- **The gap this closes (found by reading the code, not guessing):** there was **no code path to refine
  a part that lives inside an assembly.** `refine_authored` operated on a single-part run; assembly
  members were static `.py` files with no revision path. The core M4 interaction — *click the roller
  wheel, say what's wrong, watch it change* — had nothing behind it. `chat.refine_part` is that verb.
- **Shipped — `src/caliper/chat.py`:** `turn(store, message, scope=None)` → classify → act → re-measure
  → reply. It adds **no** geometry machinery; every action dispatches to the existing engine
  (`authoring.improve`, `authoring.refine_authored`, `DesignStore.restore`). What's new is the three
  things a conversation needs and the engine never had:
  1. **Scope is the selection.** Unscoped = the design, scoped = the clicked part. That one rule
     replaces the mode toggles and the "pick 1 / pick 2" ceremony.
  2. **Revisions see the design context.** `_working_spec` hands the author the goal, requirements,
     sibling parts, **mates that must keep holding**, enforced assertions, and a bounded feedback tail —
     on a *copy* of the spec, because `refine_authored` folds the instruction into `spec.intent` and
     that must not leak into the stored `spec.yaml` (tested). Multi-part designs also get an explicit
     **"build in the design's world coordinates"** instruction, since assembly parts carry no transform.
  3. **Every geometry change re-measures the WHOLE design** and the reply names what it **broke** (and
     fixed), by id, with the number. This is the thing that separates it from a chat wrapper around a
     CAD kernel.
- **Routing** mirrors intake (CALI-5): Claude when a key is present, a deterministic parser otherwise,
  injectable for tests, and it **degrades rather than crashing** — a malformed LLM reply falls back to
  offline with a stderr note. The offline rules deliberately **ask instead of guessing** when no part is
  named and nothing is being added ("5mm wider please" → a nudge to click or name a part), because a
  wrong guess spends a whole authoring run.
- **`revert` — added mid-task, because the reply was writing a cheque the handler couldn't cash.** The
  break message offered "roll back to the previous version" and there was no such verb; "roll it back"
  would have routed to *refine* and authored a revision. Now `revert_part` restores the previous
  snapshot **as a new revision** (so the undo is itself history), re-measures, and the offer names the
  phrase that actually works.
- **A part that never builds is never written.** Both `refine_part` and `author_part` require
  `res.geometry` before touching the store, so a failed revision leaves the part exactly as it was
  (tested). New parts get a baseline contract (`one_body`, `watertight`) — a spec with **no** assertions
  can never pass (`Report.all_pass` needs at least one considered check), so the author loop would have
  burned its whole round budget for nothing.
- **CLI:** `caliper chat <slug> "<message>" [--part ID] [--no-llm]` — narrates each step as it happens
  (the events `on_event` emits are exactly what CALI-31 will stream over SSE).
- **Tests:** +33 (30 `tests/test_chat.py`, 3 `tests/test_cli.py`). Routing (scope, named part, longest
  match, add-a-part, questions, ambiguity), LLM parse + target validation + fallback, honest refusals
  (unknown part, imported geometry with no script), logging, events, and the OCCT-gated core: refine
  inside an assembly rebuilds and re-measures; **a change that breaks another part is named in the same
  turn**; fixing it is reported; a non-building revision leaves the part alone; revert round-trips.
  **217 passed.**
- **VERIFIED LIVE** (real Claude calls, `caliper chat` against a seeded 2-part gantry):
  - *"make it 60mm wide and give it four M3 mounting holes on the top face"* on `carriage` → authored in
    1 round, **kept the world-coordinate `translate((0,40,0))`** (the context instruction worked), all
    checks green.
  - *"make it 120mm deep in the Y direction"* → the part itself passes every check, but the reply reads
    **"⚠ This change broke 1 design check(s) that passed before: carriage_clears_rail:
    interference(carriage, rail) <= 0 → actual=7200.0"**. Exactly the failure mode this task exists to
    catch.
  - *"roll it back"* → restored v2 as v4, **"✓ That fixed: carriage_clears_rail / The whole design
    measures green."**
- Commit: `48a35fb`

---
