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
