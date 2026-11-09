### 2026-11-06 · CALI-101 (#93) · Carve it: one click, one carve, its progress, and a cancel
- **The page error on Theo's run** ("Cannot read properties of undefined (reading 'ok')"): `makingView` read
  `m.data` while the shop plan was still loading. It says "planning…" until it's back.
- **One carve per design at a time,** checked as it's queued (`JobRunner.submit(exclusive=True)`, under the runner's
  lock), so two requests 11 ms apart can't both get through. The second gets a 409: "a carve is already running: step
  2 of 6". The page keeps the carve in `S.carveJob` from the click, so a second click (or a second handler) sends
  nothing.
  - **Why one click sent two:** not found. The page draws one Carve button and wires it once. Both guards now stop
    a double-fire whatever its cause.
- **The panel shows the carve as it runs:** the step it's on, the bar, "about N min left" from its pace so far, and
  **Cancel**. A redraw draws it again from state; a reload finds it through `design.carving`.
- **Cancel:** `POST /api/jobs/{id}/cancel`. A queued job never starts. A running carve stops at its next step
  boundary (in the sweep, or between steps) and keeps what it finished: #99's record, marked `cancelled`, with the
  best of its steps. The panel and the Studies row say "cancelled after k of n steps".
- **The label before you press** (reworked from #102's review). Until a carve of the part has finished, it's a floor:
  "at least about N min at this size". That comes from this version's default-voxel strength check (the coarsest at
  this version: a finer one asked for never sets it), × 45, the low end of what was measured: 47 on the printed box,
  67 on the mixed stool, about 65 on the bar stool's sweep, about 190 on the reviewer's tube. A ratio isn't a
  constant, so it never says "about" before a carve has finished. After one, it's that carve's own time. With no
  check: "check it holds first". With a check whose voxels didn't connect: "a carve can't run".
- **One step count:** the carve says "in 7 steps (as drawn, then 6 carved)". The panel, the 409 ("step 3 of 7"),
  the cancelled panel and the Studies row all count the same 7.
- **"Stopping…" survives a reload:** `stopping` is in the job's `to_dict` and in `design.carving`, and a cancel of a
  running job emits a `stopping` event, which a page that follows the job from the start hears.
- Tests: `tests/test_carve_click.py` (main fails 7 of the first 9; the makingView one with Theo's exact error).
  From #102's review, tests that can fail: a barrier hook between the check and the queueing (a check-then-queue
  split queues two); and node tests for the click guard, "stopping…" after a reload, following a running carve, and
  the label's cases. Each fails under the mutant the reviewer found surviving.
