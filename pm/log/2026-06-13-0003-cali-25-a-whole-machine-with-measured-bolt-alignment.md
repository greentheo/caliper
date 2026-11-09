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
