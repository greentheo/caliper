### 2026-06-12 · Assembly model — a collection of parts that fit together (CALI-20)
**New:** Caliper now represents **N parts + named mates + assembly-level assertions** and *measures*
them. Each mate (`touch` / `clearance` / `fit` / `no_interference`) between two parts becomes a measured
check — "these two seat flush", "this slips into that at a slip fit" — and `max_interference() <= 0`
proves no pair collides. This is the first step toward the north star ("insert a support between the
wheel and the XYZ assembly"): the geometry of a *machine*, not just one part.
**Try it — CLI:**
```bash
python examples/make_assembly.py          # (re)generate base/post/cap STLs (centered, local origin)
make assemble                             # measures examples/assembly.yaml → ALL PASS
#   caliper assemble examples/assembly.yaml
# → base→post→cap stack; two `touch` mates (clearance ≈ 0.000) + nothing_collides → ALL PASS.
#   Parts are posed by `position:` in the YAML; the fit probes measure them where they sit.
```
The assembly file (`examples/assembly.yaml`): `parts` (id + source STL/run-dir + position/rotation),
`mates` (between two part ids, a kind), and free-form `assert`. Bump a part's `position` so two boxes
overlap → the mate **and** `nothing_collides` both flip to `fail` with the overlap volume as the actual.
