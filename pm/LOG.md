# Caliper work log

Append-only. Newest first. One entry per shipped task or notable decision.
Format: `### YYYY-MM-DD · CALI-N · title` then what changed, tests, and the commit hash.

---

### 2026-10-27 · CALI-41 · What it's built from — weight, balance and a shopping list
- **Why:** the frame study showed the hitch carries ~6,400 lb·in standing still, dominated by weight far
  behind the pin. Theo's priorities: lighten the back (mostly foam, 1 in steel instead of 2 in), and get to a
  ~60 lb box: ⅜ in plywood floor, four 2x2 corner posts, 1 in foam + PMF everywhere else. He also wants this
  reusable, not tuned to this one project — and it's the groundwork for the cut plan and CNC DXFs.
- **Design:** a part declares `BUILD` (choices) and `construction()` (pieces), like a frame declares
  `members()`. Choices live apart from PARAMS on purpose: a drag study searches PARAMS, and a floor-thickness
  change must not make that study "stale" — `shape_signature` now ignores BUILD/construction/members/supports
  (no stored signatures existed yet, so normalising trailing whitespace was free).
- **The box (v5, shape unchanged — STL bounds identical):** floor full 74×39 in, walls standing on it, front
  and back full width, sides between, roof on top; posts in the corners inside the foam. Handles the tail
  shapes too (bent panels by facets) for when Theo picks one. **56.1 lb**: ⅜ ply 21.9, PMF 14.6, XPS 10.1,
  posts 5.4, hardware allowance 3.1, sealer 1.0. CoG 19.5 in behind its front, 14.2 in above its floor.
  Shopping list: 1 sheet ⅜ ply, 4 sheets 1 in XPS, 2 × 8 ft 2x2, 5.9 yd of 60 in canvas, ~0.8 gal glue,
  ~0.9 gal paint.
- **The design:** frame (2 in tube as drawn) **71.6 lb** at 34.9 in behind the receiver mouth + box 56.1 lb at
  40.5 in → **127.7 lb, 4,774 lb·in** standing. The frame is the bigger half — CALI-42's target.
- **Steel weight:** whittle's FrameStudy weighs with AISC's design wall (0.93× nominal) — right for stiffness,
  ~7% light for weight. Caliper weighs tubes at nominal wall with rounded corners (2x2x⅛ → 3.08 lb/ft vs a
  catalog's 3.05); whittle's 67.1 lb ÷ 0.93 ≈ 72 agrees.
- **UI:** part → **Built from**: weight, CoG, pickers for every BUILD entry (what-if, nothing saved), *Use
  these*, made-of table, *To buy*. Design → **Weight & balance** with a payload. Red dot = CoG, green = hitch.
  Verified in the browser (¼ in floor what-if → 48.9 lb, hitch 4,481 lb·in; reset).
- Tests: `test_construction.py` (18) + 3 API tests. Full suite green.
- Commit: `42f5fee`

### 2026-10-27 · CALI-40 · Size the frame — and three bugs a tube frame shook out
- **Why:** with the camper shell shaped, Theo turned to the 2 in steel underframe: "how can we whittle that
  part down to use as little steel tube as possible", plus gussets at the riser's 90-90 jog for his CNC plasma.
  Voxels can't see a 1/8 in wall at 74 in, so the tube frame is a *frame* problem. Coordinated with the
  whittle-agent session: it built `FrameStudy` (beam solver, tube catalog within 1% of AISC HSS, sweep from as
  drawn to lightest-that-passes) on its `frame-study` branch; plate mode for the gussets comes after, fed by
  the frame's end forces at the jog. Theo's calls: frame first; no legs yet (driving case only).
- **Shipped — `src/caliper/frame_study.py`:** a part declares its own structure — `members(params)`
  (centrelines, tube, group, and the PARAMS that size it) and `supports(params)` — read in a separate process.
  Ends within 1 mm merge into joints; tubes map to whittle's catalog keys; two cases: `standing` (x1, the
  number to compare with the hitch rating) and `driving` (x2.5). The sweep's chosen tubes are written back
  into PARAMS as a parametric revision. API `/api/designs/{slug}/frame-study*`; the inspector shows **Size the
  frame** (not drag shaping) for any part with members()+supports(); previews fade the other parts.
- **Result on Theo's frame (100 lb on the rails, x2.5 driving):** as drawn (2x2, 1/4 shank) 67 lb of steel,
  weakest **1.45x** (riser, driving), sags 1.24 in. **The hitch holds 167 lb and 6,394 lb-in standing still**
  (15,984 at x2.5) vs ~2,450 lb-in for a typical Class II (350 lb x ~7 in). The sweep lightens the ladder first
  (1x1 rails, 2x2x0.083 cross members: -22 lb, *safer*), then puts steel at the jog (3x3 riser and upper shank,
  2x2 solid in the receiver): **3.32x at 63 lb** — it cannot reach 3.5x with what fits a 2 in receiver. The hitch
  moment barely moves with tube sizes (5.5–6.4k lb-in): it's the 100 lb box 40 in out. Matches the agent's run.
- **Three bugs the tube frame exposed, all fixed:**
  1. **Author replies were capped at 2,000 tokens** — a seven-tube frame + members() came back cut off
     mid-line, every attempt, as a baffling SyntaxError. Cap now 8,000, and a cut-off reply fails the build
     with the real reason ("write it more compactly").
  2. **`body_count` counted air as bodies.** Where a hollow tube's open end sits inside another tube, its bore
     is a sealed pocket whose surface is a separate mesh shell — a welded frame read as 6 "bodies", which also
     derailed the LLM's last attempts. Now counts B-rep solids when present, else only outward-facing shells.
  3. **The LLM author kept misplacing tubes** (corner-anchored boxes: cross members at y -93..-30 in). After
     three rounds I wrote the frame script myself — hollow tubes hollowed individually then fused with overlaps,
     members() whose ends meet at the joints (13 members, 12 joints), supports() for the receiver socket.
- **UI:** the run picker / stale-study guard for drag studies (`043a9cb`), a back link from an accidental "+ New
  design" (`1b37143`), and previews now fade other parts (the box hid the frame).
- **The Caliper server was SIGKILLed once** (exit 137, no traceback, RSS ~0.5 GB before and after) — external,
  most likely macOS memory pressure; not reproduced.
- **Tests:** +14 (`test_frame_study` 9, `test_measure` 3, `test_authoring` 2). 62 passed across the touched files.
- Commit: `117960e`

---

### 2026-10-27 · CALI-39 (follow-up) · The first real design, and what it taught the PARAMS contract
- **Theo's answers:** receiver ~9 in off the ground and 3 in forward of the bumper; ~51 in from there to the
  roof (60 in); teardrop/hatchback rear; Class II hitch; the hatch swings at most ~14 in behind the bumper.
  Built his design in the real UI, driving the shared browser pane: `a-cargo-box-on-the-trailer` — a Leaf
  rear stand-in (hatchback profile, a guess to correct), a `hatch_swing` envelope (both references), the
  2 in tube frame, and the box (tunable: tail params at 0). Clarify answered 3, assumed 2 (rear door,
  6 in roof fan — the rear door conflicts with tapering the tail; flagged to Theo). The box request's
  "must clear the hatch swing by at least 2 in" became `min_clearance(cargo_box, hatch_swing) >= 50.8`,
  validated (4 in today) and locked in.
- **Found live — the author put PARAMS *inside* `build()` and wrote `70.5 * 25.4`**, violating both halves
  of the convention, so the reader saw nothing. Fixed both sides: `read_params` also finds PARAMS at the
  top of `build()` and folds arithmetic on numbers (rewrite replaces the whole expression span, comment
  kept); the prompt now says *first statement, outside build(), finished numbers, inches in a comment* with
  an example. The next three parts all came back in the right shape.
- **The loop doing its job:** the frame came back with its ladder running 9 in forward under the car; two
  chat corrections (scoped to the frame) fixed it, measured each time (v3: ladder exactly -57..-18 in). A
  box request I sent while the frame was still selected was — correctly — treated as a frame change; it
  failed to build in 4 rounds and **the frame was left untouched** (never write a part that won't build).
- **Engineering flags raised with Theo:** Class II usually means a 1¼ in receiver (frame shank must match);
  the box's centre sits ~40 in behind the receiver — the empty box + frame (~110 lb est.) already puts ~3,800
  in·lb there vs ~2,000–2,500 for a typical Class II rating; departure angle ~8° at a 12 in floor.
- Tests: +2 (`test_aero`). 77 passed across aero/chat/API.
- Commit: `990fe80`

---

### 2026-10-27 · CALI-39 · Shape it for drag — numbers back, not a mesh
- **Why:** Theo's ask — whittle's carving makes organic, remeshed shapes that leave the parametric world;
  he wanted whittle to "remove mass … then replace with smooth, splined surfaces", and the whittle-agent
  session had ideas for using Caliper's parametric tools so the result is "a parametric part you could
  use directly". Synced with it over SendMessage; agreed split: **whittle drives** (its new
  `ParametricStudy`, same volume-vs-drag slider), **Caliper supplies `build(params)`**, in-process.
- **The contract:** a part's key dimensions live in a module-level `PARAMS` dict, `build(params)` merges
  overrides. `aero.read_params` / `write_params` read and rewrite it with `ast` **by source position**
  (UTF-8 byte offsets — a test pins a unicode comment ahead of it), so comments, layout and the build
  function survive byte-for-byte. Every authoring prompt now requires the convention (`chat.TUNABLE`), so
  parts are born tunable; a part without it gets a "Make it tunable" button that asks the chat.
- **The gap that mattered:** design parts were built with **empty params** (`_build_py_local` calls
  `build({})`), so their scripts hardcoded dimensions — nothing for a search to vary. The convention fixes
  it without threading spec parameters through the assembly loader.
- **Speed: `sandbox.BuildWorker`.** A sweep builds the script ~1000 times; the one-shot sandbox costs a
  fresh process + CadQuery import (1–2 s) each time. The warm worker (`_build_worker.py`) keeps one
  sandboxed process, compiles the script once, answers over a dedicated pipe (OCCT writes to stdout at the
  C level), kills/restarts on a timeout. Measured: start 1.2 s, then **0.13 s per build**; a failing fillet
  is a skipped candidate and the worker carries on.
- **Live result — the hitch box behind the Leaf stand-in** (obstacles from the whittle side; 4 params,
  effort 0.3, 105 km/h): 718 builds in 171 s. Best: `tail_len 500, tail_drop 146, tail_pinch 140,
  tail_edge_r 4` mm — a ~16° boat tail on top and sides, just under the model's ~20° separation threshold —
  **drag 83%, 11 lbf ≈ 2.2 kWh/100 mi saved, 7% of the volume**. Compare CALI-38's tail-only mesh carving:
  8.5 lbf, and its stations were inflated remeshes. Here the envelope stays **exactly** 39 x 74 x 41 in.
  `tail_len` hit its 500 mm bound — a longer taper is worth trying.
- **Verified in the browser:** the inspector lists the part's PARAMS with search ranges, runs the study
  with an ETA, previews a design in place (original as a ghost), and **"Use these numbers"** writes them
  into the script → v5, still `authored`/scripted, values rounded to 0.1 mm (finer than foam holds).
  Fixed on the way: the results table overflowed the inspector and scrolled the whole panel sideways.
- **Depends on whittle's uncommitted `physics-and-slider` branch** (installed editable into the caliper env
  — dry-run clean, adds scikit-image only). Kept on its own branch until that lands.
- **Tests:** +21 (`test_aero` 15 incl. two real studies at minimal effort, API 4, chat 1, worker via aero).
- Commit: `abb1d59`

---

### 2026-10-27 · CALI-31/32/33/38 · The design session in the browser, and the whittle bridge
- **Why (Theo, back after five weeks):** he wanted to *use* it — open the UI, design something real, and
  send it to his other project **whittle** (FEA + drag optimizer) for aero/load work, then bring it back.
  The real project: a **hitch cargo box behind his Nissan Leaf** — 74" W x 41" H x 39" D, 18" behind the
  car, XPS foam + poor man's fiberglass on a 2" steel tube frame. Asked to build the UI + updates, then
  walk him through it.
- **CALI-31 — jobs + SSE (`src/caliper/jobs.py`).** Long work runs on a worker; events stream over
  `GET /api/jobs/{id}/events`. Per-key locks: jobs sharing a key serialize, different keys run side by
  side (a whittle sweep doesn't block a chat). **Lost-update guard:** quick synchronous writes (units
  toggle, clarify answers, bring-back) take the same per-design lock as chat turns — otherwise a turn
  that loaded the design before the change would save over it. Heartbeats keep a 2-minute sweep's
  stream alive; the page de-dupes by sequence number and falls back to polling if the stream drops.
- **CALI-32 — the home page is now a viewport + a conversation** (`index.html`/`design.js`/`design.css`;
  the old panel moved to `/classic`, untouched). Chat left, Z-up viewer centre, inspector right. **Click a
  part to talk about it** (scope chip); the inspector shows its size in in/mm, the rules locked in on it,
  its history, the whittle panel, and an Advanced drawer with the script/spec. Proposals get Yes/No
  buttons. The thread redraws from `log.jsonl` — which meant **logging the reply text** (it only logged
  the action before). API in its own router, `src/caliper/design_api.py`.
- **CALI-33 — clarify round (`src/caliper/clarify.py`).** A new design drafts ≤5 questions that change
  geometry, each with a default; answers become requirements, **blanks are recorded as assumed**; "Just
  build it" assumes them all. The LLM call runs *outside* the design lock. A prompt written in inches
  turns on inch display (`Design.display_units`) — geometry stays mm, and the author is told to convert
  (an author told `UNITS: in` would model 25x too small).
- **CALI-38 — the whittle bridge (`src/caliper/whittle_bridge.py`).** Caliper drives whittle's own local
  server (`POST /api/parts`, `/api/jobs`, poll, fetch stations) — **no changes to whittle**, no shared env.
  Pre-fills flow (-X), mirror y, flat bottom, speed, budget, interior keep; `flow` and `dual`. Stations
  are filed under `designs/<slug>/whittle/<run>/`; **bring one back** → the part's revision becomes a mesh
  (`DesignStore.write_mesh_part`, new `whittled` origin), its script survives underneath, and rollback
  crosses back to it. Chat refuses to revise a whittled part's stale script (that would silently throw
  the carving away) and says how to get back.
- **Three things the LIVE runs against Theo's whittle taught, all acted on:**
  1. **Sheltering by merging fails.** I sent a frozen stand-in for the car's rear in the same upload so
     whittle's drag model would see the box sitting in its wake. Every station came back **0% removed**.
     whittle's flow study deforms one FFD lattice over everything uploaded; any move that reshapes the box
     also moves the frozen stand-in, the KeepOut penalty makes it infeasible, nothing beats the start. The
     path was **removed**, not shipped. Real shelter needs obstacle bodies in whittle — raised with the
     whittle-agent session.
  2. **Free air is the wrong question for a trailing box.** Free air: 20% removed → drag 55%, ~107 lbf
     saved at 65 mph — but it gets that by rounding the *front*, which behind a car sits in the wake.
     Restricting carving to the **tail** (`carve="tail"`, whittle's own `surfaces`) is the defensible
     study: **~37.5 N (8.4 lbf) ≈ 1.7 kWh/100 mi from ~8% of the box**, plateauing there. Allowing the strips
     past the car's sides "saved" 197 N, but only because the strips had to be voxel-wide and full-length,
     i.e. it rounded the front corners again — not trusted, not offered.
  3. **whittle's stations are voxel remeshes, ~½ voxel bigger than what was sent.** Station 0 ("0%
     removed") of a 74" box came back ~1" bigger per side, **+8% volume, bottom 0.94" lower** — and the
     "20%" station was really 13% of the box. This also broke my first context-stripping (containment
     test). Now Caliper **measures** removal against the part as built (station volume / part volume),
     and bringing a station back reports every side it grew (`grew_mm`), shown in the chat as a warning.
     The fake whittle in the tests inflates its stations too, so this can't regress unseen.
- **Coordinated with the whittle-agent session** (Theo's ask): sent it the bridge, the obstacle finding,
  the inflation numbers, and a proposed **parametric loop** — Caliper owns `build(params)` (tail taper,
  edge radii: buildable in foam), whittle exposes a fast *score* endpoint on its drag model, Caliper's
  optimizer searches. A parametric part comes back, not a mesh, and the remesh inflation disappears.
  Filed as **CALI-39**.
- **Tests:** +~110 (`test_jobs` 9, `test_clarify` 12, `test_whittle_bridge` 22, `test_design_api` 25, plus
  design/chat additions). Verified in the browser end to end against the real whittle (scratch designs
  dir, `caliper-web-scratch` launch config): units toggle, click-to-scope, a station previewed in place
  with the original as a ghost, bring-back, the chat refusing to revise the mesh, "roll it back" through
  chat, marking the car as a reference, and a tail-only study streamed from the page.
- Commit: `4fe957a`

---

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

### 2026-09-18 · CALI-28 · The Design object — a container for "the thing I am building"
- **Why (Theo, picking the project back up):** the engine works, but the webapp is a *control panel for
  the engine* — it asks the user to know LLM-vs-offline, run-vs-assembly, "author any part", and which
  two parts to pick before Insert un-greys. Every toggle is an internal seam leaking into the user's
  job. The new direction: the product is a **viewport + a conversation**; you state what you're
  building, click a part, and talk about that part. Written up as **M4** in
  `specs/caliper-conversational-spec.md`, with M5 (decomposition) behind it.
- **Decisions taken up front:** chat-first on a **single part** before decomposition (don't debug a new
  planner and a new UI at once) · the old panel is **demoted to an Advanced drawer**, not deleted (the
  escape hatch matters when the loop misbehaves) · assertion promotion is **proposed and confirmed**,
  never silent.
- **The idea that makes the history worth keeping:** measurable feedback is **promoted into the spec's
  `assert` block**. "The wheel must clear the rail" becomes `min_clearance(rail) >= 1.0` — a test the
  existing evaluator enforces on every later revision. The history then splits cleanly: `history.jsonl`
  holds the narrative, `spec.assert` holds the enforceable residue. That's what keeps prompt context
  bounded as a design grows, instead of stuffing an ever-growing transcript into every revision.
- **Shipped — `src/caliper/design.py`:** `Design` / `DesignPart` / `Requirement` (pydantic, YAML+JSON
  round-trip) and `DesignStore`, the only thing that writes inside a design:
  `designs/<slug>/{design.yaml, assembly.yaml, log.jsonl, parts/<id>/{part.py, spec.yaml,
  history.jsonl, versions/vNNN/}}`.
  - **`assembly.yaml` is the existing format** — part sources are written relative to the design root
    (`parts/<id>/part.py`), which `_resolve_source` already handles, so `evaluate_assembly`/`assemble`/
    `insert` consume a design untouched. **A single-part design is a one-part assembly** — no second
    code path, which is what makes "prove it on one part, grow into machines" safe.
  - **Append-only, snapshot every revision.** `write_part` writes the canonical `part.py`, snapshots
    `versions/vNNN/` (part.py + spec + report), updates both records, and appends history **in one
    step** — so the history can't drift out of sync with the geometry it describes. `restore` rolls
    back as a *new* revision, so the rollback is itself history.
  - **Cache invalidation (subtle, would have bitten):** `assembly._PART_CACHE` keys on (path, mtime); a
    same-tick rewrite could serve **stale geometry to the very re-measure meant to prove the change
    landed**. `write_part` now evicts the entry. Covered by a test that widens a part and re-measures.
  - `adopt_run` brings an existing `runs/run_NNNN/` in: an authored run keeps its `part.py` and stays
    revisable; a template run has only geometry, so it's marked `imported` and the assembly points at
    the run dir — honest that there's nothing to revise.
  - `prompt_context(part_id)` builds the **distilled** context a revision should see: goal,
    requirements, sibling parts, mates that must keep holding, enforced assertions, and a bounded tail
    of feedback — not a transcript.
- **CLI:** `caliper design new|list|show` — `show` prints requirements, the part tree with each part's
  feedback narrative, and then **measures the whole design** (tolerant: names a broken part instead of
  sinking the rest, inheriting CALI-27's discipline).
- **Tests:** +26 (23 `tests/test_design.py`, 3 `tests/test_cli.py`) — round-trip, slug collisions,
  versioning/snapshots, torn-history-line recovery, id validation (rejects `../escape`), requirement
  upsert, bounded prompt context, run adoption both ways, and OCCT-gated proof that a design measures
  through `evaluate_assembly` and that a revision is measured rather than cached. **184 passed.**
- **Verified by hand:** created a gantry design, seeded two parts + a refine + requirements,
  `caliper design show` printed the tree, the feedback narrative, and `ALL PASS`.
- `designs/` gitignored (user artifacts, like `runs/`).
- Commit: `658c52e`

---

### 2026-06-13 · CALI-27 · Hardening — fix the things Theo actually hit
- **Reported (Theo):** (1) confusing UI — "didn't know which options to click"; (2) "adding in new
  parts didn't seem to work"; (3) "the 'machine' generation only made part of the machine";
  (4) "I don't even remember where it's hosted."
- **Root cause of the partial machine (real bug):** `loadAssembly` fetched part STLs sequentially with
  **no `response.ok` check** — one slow/failed part threw out of the loop, leaving already-added parts
  on screen and never loading the rest. Fixed: parts load **in parallel**, each with its own error
  handling; the viewer renders everything that loaded and the error bar **names what broke and why**
  (status: "loaded 3/4 parts — see the error bar"). Progress text explains the first-load script builds.
- **Server tolerance:** new `assembly.load_parts_tolerant` — one broken part no longer sinks the whole
  assembly; `/api/assembly/{id}` returns `part_errors` per part and still measures what loaded. Build
  errors now surface the traceback's **last line** (the actual exception), not 300 chars of boilerplate.
  A stale error bar is cleared on each new load.
- **UI clarity:** a collapsible **"❓ How this works"** primer (build one part → refine → fit →
  assemblies/insert; which actions need the API key); intent label says **"describe one part"** (a
  machine = an assembly — likely the other reading of "generation only made part of the machine": `gen`
  authors ONE watertight part by design); tooltips on use-Claude/author/refine; the Insert hint now
  narrates each step ("left-click a part … 1 more … ready — Insert authors a part mating a ↔ b").
- **Where it runs:** README gains a top-level "▶ Run it" block — **`make serve` →
  `http://127.0.0.1:8000`, local only, not hosted anywhere**; TESTING.md opens with the same callout.
  README status/layout refreshed (was stale at "Phase 0").
- **Verified live in-browser (Preview MCP):** a deliberately-broken 2-part assembly renders the good
  part + names the broken one ("RuntimeError: demo: this part is intentionally broken"); the corner-leg
  machine still loads 4/4 ALL PASS; pick hints step through 0→1→2 correctly; error bar clears on the
  next load; zero console warnings.
- Tests: +2 (`load_parts_tolerant` names the broken part; `/api/assembly` returns `part_errors`, good
  part still serves, broken part 422s with a clear detail). **158 passed.**
  Commit: ab9db2c

### 2026-06-13 · CALI-25 + CALI-23 + CALI-26 · A whole (small) machine, with measured bolt alignment
- **The north-star stress test, passing:** a 4-part **corner leg** — two solid **20×40 mm bars** (a
  vertical post + a horizontal beam) meeting at a right angle, joined by a **gusset bracket** and
  standing on a **foot**, screwed together with M5s through **aligned holes** — `caliper assemble
  examples/machine.yaml` → **ALL PASS** (4 touch mates, no collisions, **3 bolt-hole-alignment checks at
  ~1e-15 mm**).
- **CALI-23 — parts built from a script at assemble time:** an assembly `Part.source` can now be a
  CadQuery `build(params)` **`.py`** (not just an STL/run-dir). `assembly._build_py_local` runs it in the
  sandbox (keeps the **B-rep** — so feature probes work), cached by path+mtime; `_build_py_part` poses
  it. The machine's 4 parts are committed scripts under `examples/machine/`, built in world coords.
- **CALI-25 — hole-alignment measurement (the new vocabulary):** `measure.holes_world(g)` returns a
  part's holes transformed into the assembly frame by its `pose`; `measure.min_hole_misalignment(a, b)`
  is the smallest perpendicular offset between a hole of `a` and a *near-parallel* hole of `b` (0 =
  coaxial → a screw passes straight through both). Bound into the assembly evaluator as
  `hole_misalignment(a, b)` / `holes_aligned(a, b, tol)`. Threaded = tap-diameter holes in the solid
  bars, clearance in the bracket/foot (the real FDM convention; no modeled helix — per CALI-12).
  Added `pose` to `Geometry`.
- **CALI-26 — collision shading in the viewer:** `/api/assembly/{id}` and `/api/insert` now return
  `collisions` (pairs with interference > 0); the viewer shades any colliding part **red** (resets to
  its role color otherwise). The webapp also serves `.py` parts as STL (builds the local mesh; the front
  end poses it), so script-built assemblies render.
- **Verified:** CLI `assemble examples/machine.yaml` → ALL PASS; in-browser (Preview MCP) the corner-leg
  loads, all 4 parts render with the bracket's **bolt holes visible**, ALL PASS, no collisions/red, no
  console errors. Negative tests confirm `hole_misalignment` *grows* with offset and the assertion fails.
- Tests: `test_assembly.py` +5 (script-build keeps B-rep + detects holes; misalignment 0-when-coaxial /
  grows-when-offset; deferred without holes; full eval pass + fail). **156 passed.**
- **Deferred:** mate lines in the viewer + per-part build cache invalidation across processes; threaded
  helix modeling (CALI-12); optimizer-in-author-loop (CALI-24, still queued).
  Commit: b2e4bb9

### 2026-06-13 · CALI-21c · Viewer UX — monitor-resize, middle-mouse pan, fit-to-view + adaptive grid
- **Reported (Theo, after plugging into a different monitor):** the 3D view didn't resize correctly,
  no middle-mouse panning, and it needed a proper recenter / stage sizing.
- **Monitor/DPI resize:** `resize()` now re-applies `renderer.setPixelRatio(min(dpr, 2))` every time
  (moving monitors changes `devicePixelRatio`; the old code set it once at init → stale → blurry/
  mis-sized). CSS now sizes the canvas (`#viewer canvas { width/height: 100% !important }`) while
  three.js sets only the draw buffer — so the canvas always fills the panel and the buffer matches DPI.
  Added a `window 'resize'` listener + a `matchMedia('(resolution: …dppx)')` watcher (re-armed each
  change) to catch DPI-only changes that don't fire the ResizeObserver. Bonus: this removes the benign
  `ResizeObserver loop` warning at its source (no more inline-style feedback).
- **Panning:** OrbitControls remapped CAD-style — `mouseButtons = {LEFT: ROTATE, MIDDLE: PAN, RIGHT:
  PAN}`, `screenSpacePanning = true` (was MIDDLE: dolly). Wheel-press-drag now pans. Pick-to-select
  guarded to **left button only** so a middle/right drag pans without selecting a part.
- **Recenter + adaptive stage:** a **⤢ fit** button (and `F` key) reframes whatever's on screen
  (`frameScene`/`frameAssembly` refactored onto a shared `frameBox(contentBox())`). The ground grid is
  now **sized to the content** (`fitGrid` — rounds up to 20 mm, floor 40 mm, positioned under the
  content) instead of a fixed 400 mm plane that dwarfed small parts.
- **Verified live in-browser (Preview MCP):** canvas fills the viewer and the buffer matches DPR
  (`bufferMatchesDpr: true`); resizing the viewport 1280→1100px re-fills correctly; loading two-posts +
  ⤢ fit recenters with a content-sized grid; zero console warnings/errors. Web-only change (no Python) —
  full suite still **153 passed**.
  Commit: c4aec8c

### 2026-06-13 · CALI-21b + CALI-20b · Webapp insert UI + assembly viewer — VERIFIED LIVE
- **What it is:** the CALI-21 headline, now **clickable in the browser**. Load an assembly, see all its
  parts in 3D, **click two parts to pick the interfaces**, choose a fit + intent, hit Insert → the LLM
  authors the bridging part, it drops into the scene (green), and the whole assembly is re-measured.
- **Backend (`server.py`):** `GET /api/assemblies` (lists every YAML under `CALIPER_ASSEMBLIES`, default
  `examples/`, that parses as an Assembly), `GET /api/assembly/{id}` (parts + poses + stl_urls + measured
  report), `GET /api/assembly/{id}/part/{pid}.stl` (serves a posed part's STL), `POST /api/insert`
  (wraps `insert.insert_part` → persists the authored part as a run → `add_part_to_assembly` → saves
  `<id>.inserted.yaml` → re-measures → returns the new part's stl_url + report + script + bridge info).
- **Frontend (`app.js`/`index.html`/`style.css`):** an Assemblies list; multi-part rendering (each part
  posed, colored by role — gray=fixed, blue=movable, **green=inserted**); **click-to-pick** via raycast
  (drag vs click disambiguated by pointer travel) with emissive highlight + a picks readout; an insert
  panel (intent / id / fit); the assembly report reuses `renderReport`. `window.__asm` debug seam
  (mirrors `__caliperSM`). Benign `ResizeObserver loop` warning filtered from the error bar.
- **Bug found & fixed (live):** `insert_spec` resolved a part `source` against `base_dir`, then
  `improve`→`load_references` re-resolved the *relative* result against `ref_base` → doubled the dir
  (`examples/examples/post.stl`). The CLI dodged it (it passed an absolute base_dir); the server's
  relative `examples` exposed it. Fix: `insert_spec` stores **absolute** reference paths.
- **VERIFIED LIVE in the browser (Preview MCP, real Claude API):** loaded `two-posts`, both posts render
  at x=±30; picked both (highlight + button enable confirmed); Insert → LLM authored the cross-bar in
  **1 round**, rendered green between the posts; report ALL PASS (both mates **0.21 mm**, nothing
  collides); saved as `insert_demo.inserted`. No console errors.
- Tests: `test_server.py` +5 — list/get assembly + serve part STL + insert route-through (faked author)
  + bad-between 400 + unknown-assembly 404. **153 passed.**
- **Deferred:** in-browser assembly *authoring* (build parts from intent at insert time) → CALI-23;
  per-part red/green collision shading → polish (the report already shows per-mate pass/fail).
  Commit: 914a791

### 2026-06-12 · CALI-21 · Insert-into-assembly — the north-star headline, end to end
- **What it is:** *"insert a support between the wheel and the XYZ assembly."* The whole spine converges:
  CALI-20 (the posed existing parts + N-body measurement) + CALI-19 (fit bands) + CALI-16/17/22 (the
  author loop) → the LLM writes a part **in assembly/world coordinates** that mates to two named
  interfaces at a target fit, **verified by measurement**, then it's added back to the assembly.
- **`insert.py`:** `insert_spec(asm, between, fit, …)` builds a spec whose **references are the existing
  parts, posed** and whose assertions are the two fit **bands** + no-interference with every other part
  + one-body/watertight. `_bridge()` finds the separation axis + the two facing faces; the enriched
  intent hands the author the interface bboxes, the gap, and the facing-face coordinates in world space
  so it builds *in place* (not at the origin). `insert_part()` runs the author loop; `add_part_to_
  assembly()` appends the new part (run-dir source, identity placement) + two `fit` mates.
- **CLI** `caliper insert <asm> --between a,b --as id --intent "…" --fit slip --save out.yaml` (+ `make
  insert`): authors, persists the part (STL + `part.py`), adds it to the assembly, and **re-measures the
  whole assembly** with the new part in place.
- **VERIFIED LIVE (real Claude API):**
  - `insert` two-posts (50 mm gap) → the LLM authored a cross-bar **first try (1 round)**, landing
    **0.21 mm clearance to each post** (dead centre of the slip band 0.12–0.30); the script reasons from
    the interface bboxes, applies the clearance, and `.box(...)` in world coords. Assembly re-measured →
    ALL PASS (`crossbar_post_left`/`right` at 0.21, nothing collides). Saved assembly re-`assemble`s green.
  - Also confirmed the other LLM paths live: `gen` (authored a 4-hole part, 1 build-heal + 1 revision);
    `refine` of an authored part ("6 mm taller in z") — edited the real `part.py` (`bar_height = 10+6`)
    while keeping both fits at 0.21 (CALI-22 `refine_authored` seeding).
- Tests: `test_insert.py` (6) — bridge-axis, spec (posed refs + fit bands + no-collision + one-body),
  bad-interface guards, add-to-assembly mates, end-to-end author (injected) that mates both. **148 passed.**
- **Deferred:** webapp insert UI → CALI-21b; assembly parts built from a spec/intent at assemble time →
  CALI-23. Insert authors the geometry directly today; the multi-param optimizer (CALI-19b) isn't yet
  folded into the authored path (LLM revises dimensions instead).
  Commit: 7fb4d32

### 2026-06-12 · CALI-19b · Multi-parameter optimizer — joint tuning for coupled fits
- **Why now:** CALI-19's tuner is **1-D** (one knob per failing check). Assembly fits *couple*: one
  clearance depends on two dimensions, or two mates fight over the same wall. Tuning one knob at a time
  stalls at a saddle the per-axis sweeps can't leave. The assembly spine needs joint N-D tuning.
- **`decide.tune_multi(spec, params, eval_fn, engine="coord")`:** searches the joint continuous space
  against a **global** objective — maximize `(all_pass, #passing, worst signed margin, −total
  normalized change)`. Worst-margin drives every assertion toward/over its threshold at once;
  change-from-init keeps the solution snug.
- **Engine = coordinate descent by default** — deterministic and *eval-frugal* (geometry rebuilds are
  the expensive thing): sweep each knob over a coarse grid + a refined local window against the global
  score, until a sweep stops improving. **Escalates to a global `scipy.optimize.differential_evolution`
  (seeded, deterministic) ONLY if coordinate descent can't reach feasibility** — i.e. the genuinely
  coupled case CD traps on. Cheap-first keeps separable problems off the expensive path.
- **`decide` route 0 (CALI-19b):** with ≥2 continuous knobs and a failing numeric check, tune the whole
  vector jointly; taken only if it improves (more passing / all-pass), else fall through to the 1-D +
  snug path. Single-knob specs are untouched — the common case stays 1-D.
- Tests: a deliberately **coupled** 2-knob problem (gap band on `W+D` + budget on `W*D`, feasible only
  asymmetric) — coordinate descent escalates to scipy and solves it; `engine="scipy"` solves it
  directly; a **separable** 2-knob problem is solved by CD alone (scipy spy asserts it's never called);
  `decide` routes coupled failures to the multi move. **142 passed.**
  Commit: a84397b

### 2026-06-12 · CALI-22 · Author-loop fit & refine — edit the real part, not a bracket
- **Why now:** the fit bug Theo hit — fit/refine rebuilt via the bracket generator, so they ignored an
  authored `part.py` (CALI-19 guarded them to *fail honestly*). Now they **edit the real part**: route
  through `improve()` **seeded with the existing script**, so the LLM revises `part.py` to clear a
  reference or apply a plain-language change — the front edge of CALI-21 (insert-into-assembly).
- **`authoring.improve(..., seed_script, seed_feedback, ref_base)`:** primes round 1 with an existing
  part + the new constraint, so the model revises rather than starting over. Same build-error +
  failing-measurement healing as `gen`.
- **`refit_authored(spec, script, …)`** — spec already carries the reference + fit assertion(s) (via
  `fit.attach_reference`); seeds the loop with `part.py` and feeds the fit checks. **`refine_authored(
  spec, script, instruction, …)`** — folds the instruction into `spec.intent` (so a later round can't
  quietly undo it) and seeds the loop.
- **CLI:** `caliper fit <authored-run> --fit slip` and `caliper refine <authored-run> "…"` now route
  through the author loop (no more "refuse authored" return-2). **Webapp:** `/api/fit` + `/api/refine`
  do the same (the 422 guards are gone); a shared `_finish_authored()` persists script+STL+refs.
  `/api/gen` refactored onto it too.
- Tests: `improve` seed-priming; `refit_authored` drives a 60→30 mm box to clear a reference (2 rounds,
  fed the failing `interference`); `refine_authored` intent-fold; CLI fit+refine route-through; server
  `/api/fit` + `/api/refine` route-through (replacing the old 422 guards). **138 passed.**
- **Live (LLM) path** needs `ANTHROPIC_API_KEY`; the routing is verified deterministically via injected
  authors. Webapp/CLI live runs are Theo's to drive.
  Commit: 72b0df4

### 2026-06-12 · CALI-20 · Assembly model — N parts + named mates + assembly assertions
- **Why now:** the single-part loop is complete; the north star ("a 3D printer 10ft tall", "insert a
  support between the wheel and the XYZ assembly") is fundamentally about *a collection of parts that fit
  together*. This is the heart of the assembly spine — and the lesson from the phone-stand failure
  (complexity scales by **decomposition into well-fit parts**, not one monolith).
- **`assembly.py`:** three pydantic models mirroring the single-part spec — `Part` (id + geometry
  `source` + **placement** position/rotation, role fixed|movable), `Mate` (a **named relationship between
  two parts**: `no_interference` / `clearance` / `fit` / `touch`), `Assembly` (parts + mates +
  assembly-level assertions). YAML/JSON round-trip; validates mate part-refs + dup ids.
- **Each mate expands to one measured assertion** (`mate_assertion`): "wheel & support mate at a slip
  fit" → `0.12 <= min_clearance(wheel, support) <= 0.30` — measured, not eyeballed. `touch` → a flush
  band `-tol <= min_clearance <= tol`; `fit` reuses CALI-19 fit bands.
- **`measure.py` — N-body substrate:** `pairwise_interference(parts)` (every unordered pair),
  `max_interference()` (worst overlap — "nothing collides"), `min_pair_clearance()` (tightest gap). The
  two-body probes already accepted any Geometry pair, so N-body = run the pair probe over every pair.
- **Evaluation reuses the single-part evaluator wholesale** — same safe AST interpreter, same signed
  margins (so a fit *band between two parts* is tunable too), same `Report`. Only the namespace differs:
  part ids → posed `Geometry`, fit probes take **two parts**. Posing is baked at load (`from_stl_posed`),
  so parts are measured *where they sit*.
- **`caliper assemble examples/assembly.yaml`** (+ `make assemble`) loads, lists parts/mates, measures.
- **Verified live:** the demo `post-stand` (base → post → cap, two `touch` mates + `max_interference()
  <= 0`) → **ALL PASS** (clearances 0.000, no collisions). A deliberately-overlapping pair → both the
  mate and the assembly assertion `fail`.
- Tests: `test_assembly.py` (13) — model round-trip/validation, N-body helpers, mate expansion,
  end-to-end posed-STL evaluation (pass + fail + fit band). **134 passed.**
- **Deferred:** webapp assembly viewer (multi-part 3D + mate viz) → CALI-20b. CLI + model + measurement
  is the substance; the viewer is presentation.
  Commit: c24aa9f

### 2026-06-12 · CALI-19 · Tolerances & fits as first-class
- **Why now:** the phone-stand failure (user-reported) was mostly *bad assertions*, not bad geometry —
  a contradictory `slot_fits_phone: 8 <= bbox.dx <= 12` (the part is ~75 mm wide; `bbox.dx` is the whole
  part, not the slot) + measurement noise (`min_wall 2.99` vs a hard `≥3.0`). The fix is a fits/tolerances
  vocabulary, not a smarter prompt alone.
- **`tolerance.py`:** printer-friendly **fit classes** (press/snug/slip/free/running) → `(lo, hi)`
  clearance bands (FDM ~absolute). Helpers `approx(x, nom, tol)`, `within`, `fits(clearance, kind)` bound
  into the evaluator namespace.
- **Evaluator:** two-sided band margins — `lo <= x <= hi` now yields a signed margin (distance to the
  nearest bound) so a fit band is **tunable** (was `None`). **Optimizer:** `tune_continuous` gains
  progressive refinement (4 shrinking rounds) to converge onto a narrow 0.2 mm band; `decide` skips the
  snug `prefer` for band targets so they centre in the band.
- **Surfaces:** `caliper fit --fit slip [--nominal]` + a webapp **fit-class dropdown** → a band
  assertion. Intake taught to prefer `approx`/bands over `==`/hard thresholds and to **never** assert an
  internal feature (slot) via `bbox.*` (the phone-stand bug, at the source).
- **Verified live:** `fit --fit slip` tuned a bracket **60 → 41.8 mm** → clearance **0.188 mm**, centre
  of the slip band. Browser dropdown wired + no console errors.
- **Also fixed the fit bug they hit:** fit/refine now **refuse LLM-authored parts** (part.py present)
  with a clear message instead of silently rebuilding a bracket — CLI + `/api/fit` + `/api/refine`.
  Proper fix (route through the author loop) tracked as CALI-22.
- Tests: `test_tolerance.py` (8) + band-margin + fit-class loop + authored guards. **121 passed.**
  Commit: 7d237cf

### 2026-06-12 · CALI-17 · Structural-edit loop — fix failing measurements, not just builds
- **Closes the two-actor loop** for LLM-authored parts (design spec §2/§5): the LLM revises its own
  script when a *measurement* fails, the same way CALI-16 healed build errors.
- **`authoring.improve(spec, author, max_rounds)`:** each round the LLM writes/revises `build(params)`,
  we build it sandboxed + measure it; a build error feeds back the **traceback**, a failing assertion
  feeds back the **report** (id + expr + actual + margin). Stops on green, an unchanged failure
  signature (oscillation), or the round cap — mirrors the bracket loop's rails (CALI-6). Author is
  injectable → fully tested without a key. Folds CALI-16's build-heal into the same loop.
- **CLI:** `caliper gen` now uses `improve` (`--max-rounds`), printing rounds + heals/revisions.
- **Webapp:** `POST /api/gen` (refactored `_finish()` shared with the bracket `_execute`) + a
  **"✦ author any part"** toggle that routes Build → `/api/gen`; the authored `part.py` is shown and
  persisted; `get_run` returns it so a reloaded gen part shows its script.
- **Verified live (CLI):** `gen "a hexagonal pen cup…"` → 4 rounds (2 build-heals + 2 revisions),
  honestly reported **"best effort"** — the 2 residual fails were a *contradictory intake-drafted
  assertion* (a hexagon can't be 60×60 in bbox) and *measurement noise* (min_wall 2.99 vs hard ≥3.0),
  not author misses. Good integrity signal — it doesn't fake a pass.
- **Verified in browser (Preview MCP):** "✦ author any part" → "a round coaster, 90mm, 4mm, 3mm raised
  lip" → **ALL PASS in 1 round**, rendered in 3D, authored CadQuery shown in the script panel. No
  console errors.
- Tests: 4 `improve` tests + `/api/gen` server test. **110 passed.** Commit: 6ee3e52
- Roadmap stamped: next is the **assembly spine** — CALI-19 (tolerances & fits), CALI-20 (assembly
  model), CALI-21 (insert-into-assembly).

### 2026-06-12 · CALI-16 · LLM-authored generator (the spec's primary strategy)
- **Why:** the MVP shipped one hardcoded part family; the LLM only drafted a spec. The design spec's
  headline generation strategy (§2) is an **LLM-authored parametric script**. This builds it — the
  difference between "a bracket parameter optimizer" and the measurement-grounded vibe-CAD loop.
- **Sandbox** (`sandbox.py` + `_sandbox_runner.py`): authored scripts run in a **subprocess** (timeout,
  temp cwd), export **STEP** (keeps the B-rep so hole/face probes survive the process boundary), parent
  re-imports → `Geometry`. Any failure → structured `{error, traceback}` (the "stack trace" channel).
  Local-trust threat model; a hard sandbox (container/net-cutoff) is logged for untrusted use.
- **Author** (`authoring.py`): spec → `build(params)` script; on build error, retry with the traceback
  (bounded). The LLM call is **injectable** so author+heal is fully tested without a key.
- **CLI/wiring:** `caliper gen "<intent>"` / `make gen` — intake → author → build (self-heal) → measure
  → report → persist, storing `part.py` (the human-editable source of truth). Bracket path untouched.
- **Verified live** (claude-sonnet-4-6): `gen "a cylindrical desk cable grommet, 40mm OD, 30mm bore,
  25mm tall, 5mm flange"` → the LLM wrote a real hollow **tube + flange union** (with reasoning
  comments), built on attempt 1, watertight, correct OD/height/printable walls, **7/8 asserts pass**.
  The 1 fail is a measurement nuance (`largest_through_bore` counts the tube's outer wall as a bore →
  CALI-18), not an authoring miss.
- **Two LLM-intake bugs fixed along the way** (intake/refine had been silently dead for this model):
  (1) the **assistant-prefill** trick (`{`) made `claude-sonnet-4-6` 400 → always fell back to the
  offline bracket; removed it. (2) **schema-laxness** — model drafts didn't match the schema; added a
  precise schema+vocabulary prompt and `normalize_spec_dict()` (tolerant coercion). Now `gen` produces a
  faithful `desk_cable_grommet` spec, not a bracket.
- Tests: `test_sandbox.py` (5) + `test_authoring.py` (6) + CLI gen wiring + intake-normalize. **105
  passed.** Commit: c44403a

### 2026-06-12 · CALI-10 · Webapp fit UI + reference pose (in-3D placement)
- **Why:** fit was computed in baked coordinates — the reference had no pose, so it only "worked"
  because the demo obstacle STL was hand-authored in the bracket's frame. Real STLs (centered on their
  own origin) would land on top of the part. Fix: give references a **pose** and let you set it in 3D.
- **Reference pose:** `Reference` gains `position` (mm) + `rotation` (deg, three.js XYZ euler).
  `measure.pose_matrix` (scipy `XYZ` intrinsic, matches three.js) + `Geometry.from_stl_posed` bake the
  pose at load, so the fit probes stay pose-agnostic and the measured pose == what you see.
- **Backend:** `POST /api/fit` (base64 reference STL + pose + clearance/no-overlap + optional `free`
  param) → attaches a posed reference, promotes a size param, runs the loop, persists. Reference STL is
  copied into the run dir + recorded in `meta.references` (pose + serve url); served at
  `/api/runs/{id}/ref/{ref_id}.stl`; `get_run` returns references so a reloaded fit re-renders. Shared
  fit logic factored into `caliper/fit.py` (used by CLI + server; CLI `_cmd_fit` refactored onto it).
- **Front end (no-build):** vendored `TransformControls` (r160). Import an STL → renders
  **semi-transparent** with a move/rotate **gizmo** (W/E keys, mode buttons) → **Fit** reads the pose,
  POSTs, swaps in the resized part. The viewer now renders the part in its **true build frame** (no
  `geom.center()`) and frames on the combined part+reference bbox, so both share one coordinate system.
  Loading a past fit run re-renders its reference at the stored pose.
- **Verified in a real browser (Preview MCP):** build → import a box STL (gizmo appears) → Fit → server
  resizes + re-renders; loaded run_0026 shows the blue bracket pulled back from the orange reference at
  `[52,0,2]` with ALL PASS and `min_clearance(obstacle) actual=3`. No console errors.
- **Known caveat:** `/api/fit` is synchronous; a *coincident full-bracket* reference took ~30s (many
  mesh booleans × optimizer samples). A simple obstacle box is seconds. Logged as a follow-up.
- Tests: `tests/test_server.py` fit end-to-end + 404 (now **92 passed**). Commit: 6f048a8

### 2026-06-12 · CALI-10 · References / fit-to-reference (M3)
- **Measurements (real now, no longer deferred):** `measure.interference(g, ref)` → overlap volume in
  mm³ via a robust mesh boolean (manifold3d), with an AABB short-circuit and a containment-sampling
  fallback if the boolean kernel is missing; `measure.min_clearance(g, ref)` → signed gap in mm
  (positive = thinnest air gap from surface-proximity sampling, negative = deepest penetration). Both
  operate on meshes so they work directly on imported STL references. A `_as_mesh` coercer accepts a
  `Geometry`, a raw mesh, or a wrapper.
- **Reference binding:** `evaluate.load_references(spec, base_dir)` loads each `role: fixed` STL into a
  `Geometry`; `build_context`/`evaluate` take a `references=` map and bind `interference`/`min_clearance`
  to the real geometry. An *unloaded* reference resolves to an opaque handle so a fit check errors
  loudly instead of silently passing. `loop.make_eval_fn(references=…)` loads once and caches.
- **Snug fit:** `decide` auto-routes any failing `interference`/`min_clearance` assertion to a size
  parameter (`FIT_PARAM_PREFERENCE`), no per-spec id wiring. `tune_continuous(prefer=…)` adds a
  minimal-change objective: among feasible candidates pick the one closest to the original size, so the
  part shrinks *just enough* to clear (not down to the floor).
- **CLI/UX:** `caliper fit SOURCE --ref ID=FILE.stl [--min-clearance MM] [--no-overlap] [--free PARAM]`
  attaches the reference + fit assertion(s), promotes a fixed size param to a continuous range, runs the
  loop, persists a new run. Defaults to no-collision if no constraint given. `make fit`. Demo fixture
  `examples/obstacle.stl` (+ `make_obstacle.py`); `.gitignore` keeps `examples/**/*.stl`.
- **Verified end-to-end:** 60mm bracket vs a block at x∈[42,62] → fit shrinks the leg to 39mm for a
  clean ≥2mm clearance (`min-clearance 2`), or to 42mm just-touching for no-overlap. Tests:
  `tests/test_references.py` (11) + 2 CLI fit tests; updated the two evaluator/measure tests that
  assumed deferral. Full suite **90 passed**.
- Commit: d402e38

### 2026-06-12 · CALI-15 · Recent parts (+ hole-count hang fix)
- Browse/load past runs instead of always generating new. Persist `report.json` + `meta.json`
  (part, status, label, timestamp) per run; `GET /api/runs` (list) + `GET /api/runs/{id}` (load spec +
  report + STL without rebuilding; re-evaluates only for legacy runs). Front end: "Recent parts" panel,
  click to load the spec/report/mesh, active highlight, refresh after each run/refine; refine forks a new run.
- **Bug found while testing (real hang):** intent "…for **2020** with **two** M6 holes" mis-parsed the
  extrusion size 2020 as the hole count → generator tried to drill 2020 holes → CadQuery hung (POST
  never returned). Fixed: `_parse_holes` anchors the count on "holes" and limits it to a 1–2 digit /
  word number (so 2020 can't be the count) + clamp 1–12; defensively clamp `holes_per_leg ≤ 8` in the
  generator so no bad count can ever hang the kernel.
- Verified in-browser: build (1 iter, fast), new part tops the list with its label/timestamp, clicking
  an older run loads it (incl. legacy re-evaluate). Tests: **76 passed** (+5: list/load, parse, clamp).
- Commit: b582b54

### 2026-06-12 · CALI-9 · SpaceMouse: grid rotates with the part
- Feedback (real-use): with the SpaceMouse, the part rotated/panned/zoomed but the ground grid didn't
  rotate (it panned/zoomed fine). Cause: rotation spun the model *group* while the grid was parented to
  the world; pan/zoom move the camera so the grid followed those but not rotation.
- Fix: parent the GridHelper to `modelGroup` so rotation carries the plane with the part — pan/zoom
  (camera) and rotation (group) are now visually consistent. Verified render (no regression); rotation
  feel pending Theo's confirmation on hardware. 71 passed.
- Commit: cae162f

### 2026-06-12 · CALI-14 · SpaceMouse NL-Proxy (driver coexistence) — phase 1
- WebHID needs the user to quit 3DxWare (raw HID can't be shared — confirmed on Theo's SpaceMouse
  Compact `256f:c635`: "Failed to open the device" while the driver holds it). CALI-14 adds a *driver*
  path that coexists with Fusion.
- Researched the integration: NL-Proxy at `https://127.51.68.120:8181/3dconnexion/nlproxy`, WAMP/WSS,
  a driver-installed cert, and 3Dconnexion's `_3Dconnexion` lib driving the camera via navlib callbacks.
- Phase 1 shipped: UI mode toggle (WebHID | Driver/NL-Proxy beta); driver mode loads the proxy lib,
  instantiates `_3Dconnexion`, attempts connect, and reports the API surface + errors on-screen (cert
  hint included). Verified the graceful-failure path in the preview (no driver → clear error, no crash).
  Cannot verify the happy path here — needs Theo's hardware + 3DxWare; phase 2 (camera nav) follows the
  on-screen telemetry. 71 passed.
- Commit: 9420ca8

### 2026-06-12 · CALI-9 · webapp fix — vendor three.js locally (no CDN)
- Bug (real-use): on Theo's machine the Build button did nothing + a 404 in devtools. Cause: three.js
  was imported from the **unpkg CDN**; when that's blocked/offline/flaky the module import fails and
  `app.js` never finishes loading, so no event handlers attach. (Worked in the test browser where the
  CDN resolved — hence missed.)
- Fix: **vendor three.js locally** (`web/static/vendor/three/` — three.module.js + OrbitControls +
  STLLoader) and point the import map at local paths. App is now self-contained and works offline.
- Also: `<link rel="icon" href="data:,">` to kill the noisy favicon 404; an on-page error bar that
  shows load/runtime errors (so a dead button is never silent again); recursive package-data glob.
- Verified in-browser: zero external requests (all `localhost`), build → ALL PASS + render. 71 passed.
- Commit: 95a2e4a

### 2026-06-11 · 🎉 M2 COMPLETE · CALI-9 · webapp + SpaceMouse
- **FastAPI backend** (`server.py`): `/api/run`, `/api/refine`, `/api/runs/{id}/part.stl`,
  `/api/health` — reuse the library; persist runs; serve a no-build front end. `caliper serve` +
  `make serve`.
- **Front end** (`web/static`, no build step — three.js ESM via import map): intent box, refine box,
  measurement report panel (✓/✗ + margins + changes + clarify question), spec view, STL download, and
  a three.js viewer (STL loader + orbit, grid, lighting).
- **3Dconnexion SpaceMouse** (Theo's key ask) via **WebHID**: "Connect SpaceMouse" button →
  `navigator.hid`, 6DOF int16 axes → model rotate + camera pan/dolly, deadzone/gains tweakable, live
  axis readout, graceful fallback to mouse. Works in Chrome/Edge over localhost.
- **Verified in a real browser** (preview MCP): page loads error-free, `Build it` → ALL PASS report +
  bracket rendered in 3D; `Refine "make the holes 8mm and add a rib"` → "hole Ø 5.2 → 8.0, rib 0→1",
  re-measured, viewer reloaded the new mesh; STL downloads. Screenshotted both.
- Fixes found via the browser/test loop: FastAPI body models must be module-level under
  `from __future__ import annotations` (else 422); refine parser now handles "8mm" (no space) and
  prefers an explicit mm value over an M-size; a TDZ bug (`smOn` read before init in the render loop);
  dev `Cache-Control: no-store` so the browser never serves a stale module.
- Tests: **71 passed** (added server tests via FastAPI TestClient + refine regressions).
- Commit: 3c78fff

### 2026-06-11 · CALI-1.M1 · refine parser — per-side & word-number hole counts
- Real-use gap: "only do one hole on each side … in the middle" wasn't recognized (parser only knew
  digit + plural "N holes" as a *total*).
- Now the count parser accepts singular "hole", word-numbers ("one".."ten"), and **per-flange**
  phrasing ("on each side", "per leg") → doubles to the total. A single hole per flange is centred
  by the generator's positioning; "middle"/"centre" is acknowledged in the change list.
- Tests: **63 passed** (added 2). Verified the user's exact instruction → hole count 4 → 2,
  `bolt_pattern count=2`, ALL PASS, new STL.
- Commit: c9523c8

### 2026-06-11 · 🎉 M1 COMPLETE · CALI-1.M1 · refinement loop (one iteration cycle)
- New `refine.py`: a natural-language refinement → mutated spec. Offline deterministic parser for the
  common bracket edits (hole Ø, hole count, bolt spacing, wall, cable bore, ribs) plus an LLM path
  with offline fallback. Crucially mutates the *generator-read parameters* and re-syncs dependent
  assertions (e.g. a hole-Ø change updates both `hole_d` and the `bolt_pattern` assertion), so the
  change flows to the mesh, not just the acceptance text.
- Wired hole geometry into the generator: `BracketParams.from_spec` now reads `hole_d`/`hole_count`;
  intake emits them as parameters. (Backward compatible — defaults unchanged.)
- CLI: `caliper refine <run-dir|spec> "<instruction>"` loads a prior run, applies the change, re-runs
  the loop, emits a new run/STL. `_run_and_emit` shared with `run`. `make refine` target added.
- Demo: `run` → 4×Ø5.2; `refine "make the holes 8 mm"` → `bolt_pattern` re-synced to diameter=8.0,
  ALL PASS, new STL whose bytes differ (geometry changed; same triangle count). Optimizer tune
  already lived in the loop (CALI-6/7), so this completes the M1 "one NL refinement + one tune" cycle.
- Tests: **61 passed** (M1 added 14, incl. an OCCT end-to-end proving the rebuilt part has 4×Ø8 holes).
- Commits: `f78da23` (refinement loop), `cd857a4` (`make refine` target).

### 2026-06-11 · CALI-0 · canonical OCCT env via micromamba (Plan B) + zero-activation workflow
- Anaconda's classic solver stalled 55+ min on cadquery. Switched to standalone **micromamba**
  (osx-arm64), which solved + built the env in <1 min at `/opt/anaconda3/envs/caliper`:
  **cadquery 2.7.0 / occt 7.8.1 / ocp 7.8.1.2 / python 3.11**. Then `pip install -r requirements-pip.txt`.
- cadquery 2.7 dropped the `nptyping` dep → no numpy shim needed (unlike the pip-2.4 scratch venv).
- **`make test` → 47 passed** in the canonical env (auto-resolves the prefix), confirming the code
  works on cadquery 2.7 (not just the 2.4 used for the earlier scratch verification). CLI run → STL ✓.
- Editable-installed the package (`caliper` command) and added `make install`/`make run` targets that
  resolve the env python directly — no shell activation needed. Updated README/environment.yml to
  recommend the micromamba recipe.
- Commits: `e999d31` (micromamba env), `2c64680` (make targets + zero-activation docs).

### 2026-06-11 · 🎉 M0 COMPLETE · CALI-2/4/8 verified end-to-end with real geometry
- Verified the OCCT-dependent path. Fixed a generator bug: the CadQuery `"XZ"` plane normal is
  `(0,-1,0)`, so `extrude` is sign-defined and left the body off-centre on Y (bolt holes landed at
  the flange edge). Now recentre from the actual bounding box.
- **CALI-4** generator confirmed: corner bracket builds watertight, one body, 4×Ø5.2 holes on the
  bolt circle, optional Ø10 cable bore.
- **CALI-2** B-rep hole detection + `holes_matching(on=circle(60), count=4)` confirmed.
- **CALI-8** `caliper run "...four M5 holes and a cable pass-through" --no-llm --yes` → draft spec →
  clarify gate → loop → **ALL PASS** (bbox [60,20,60], min_wall 2.99, 4×Ø5.2 ✓, mass 8.1 g,
  watertight 1 body, bore Ø10) → 128 KB `runs/run_0000/part.stl`.
- **Full suite: 47 passed.** Verified in a pip CadQuery scratch venv (numpy-2 alias shim for the
  abandoned `nptyping`) because the conda env was still solving; re-confirmed later in the conda env.
- Commit: `ff8e154`.

### 2026-06-11 · CALI-6, CALI-7, CALI-8 · loop controller, decide, CLI
- **CALI-7** decide: continuous route (1-D grid+refine optimizer over a continuous param, scored by
  all_pass/pass-count/margin) and a structural route (bump a discrete param); defers to LLM when
  neither applies. Verified: a mass-over-budget failure is fixed by tuning `wall`.
- **CALI-6** loop controller: generate→build→sense→evaluate→decide with iteration cap, oscillation
  detection, run persistence (`runs/<id>/` spec+report+STL). Verified: converges, caps, detects
  oscillation, surfaces build failures. Injected `eval_fn` keeps it kernel-free for tests.
- **CALI-8** CLI: `caliper run "<intent>"` one-shot; `--no-llm`/`--yes` for reproducible runs; the
  ask-don't-assume clarify gate blocks non-interactive builds. Gate verified; end-to-end smoke
  (real STL) is OCCT-gated.
- Whole suite: **39 passed, 4 skipped** (CadQuery-only) in a clean venv.
- Commit: `a223b13`.

### 2026-06-11 · CALI-1, CALI-3, CALI-5 verified; CALI-2, CALI-4 written
- **CALI-1** spec schema: pydantic models (continuous/discrete/fixed params, references, machine stub,
  assertions under the `assert` alias); lossless YAML/JSON round-trip; validation on bad input.
- **CALI-3** evaluator: safe AST interpreter (no `eval`), signed margins for comparisons, compound
  `and` reports the binding margin, deferred probes (e.g. `interference`) marked `deferred` not failed.
- **CALI-5** intake: deterministic offline drafting for the bracket family (parses size, hole spec,
  extrusion width, cable), ask-don't-assume clarify gate, LLM path with offline fallback.
- **CALI-2** measurement API: mesh side verified (bbox, volume, mass, watertight, body_count, ray-cast
  `min_wall_thickness`, deferred probes); B-rep hole detection written, OCCT-gated.
- **CALI-4** corner-bracket CadQuery generator written (L-profile extrude, per-leg bolt holes, optional
  ribs + cable bore, structured build-error capture); OCCT-gated.
- Tests: **29 passed, 3 skipped** (CadQuery-only) in a throwaway venv. Added `rtree` dependency
  (trimesh ray casting needs it for `min_wall_thickness`).
- Commit: `0d93efa`.

### 2026-06-11 · CALI-0 · project scaffolding + environment
- Initialized local git repo. Created `src/caliper/` package layout, `tests/`, `pm/`, `nightshift/`.
- Stood up the .md PM system: `BOARD.md`, `TASKS.md`, `LOG.md`, `pm/README.md`.
- Adopted ai-night-shift conventions locally (loop/review/test guard) without cron — see `nightshift/`.
- Env: moved all non-OCCT deps to a pip layer (`requirements-pip.txt`) so conda only resolves
  `cadquery` under strict conda-forge priority (the full mixed-channel solve stalled).
- Decisions: conda for the env; nightshift conventions-only (no autonomous cron yet); start M0 core.
- Commits: `aa00b5d` (scaffolding + M0 skeleton), `45cd6b9` (lean conda env).
