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
