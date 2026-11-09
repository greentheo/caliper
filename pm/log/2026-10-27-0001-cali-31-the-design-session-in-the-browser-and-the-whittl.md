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
