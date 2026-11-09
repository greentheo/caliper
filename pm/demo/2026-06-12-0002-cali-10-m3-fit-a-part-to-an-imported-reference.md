### 2026-06-12 · M3 — fit a part to an imported reference (CALI-10)
**New:** `caliper fit` takes a part you already made and an imported STL, and resizes the part until it
clears that reference. Two checks are measured exactly on the meshes: `interference` (overlap volume,
0 = no collision) and `min_clearance` (smallest gap, negative if they interpenetrate). The optimizer
shrinks the part **snugly** — just enough to clear, not down to a stub.

**Try it (needs cadquery env):**
```bash
# 1) make a part to fit, and the demo obstacle (a block parked against the bracket's flange end)
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"   # → runs/run_0000
python examples/make_obstacle.py        # writes examples/obstacle.stl (already committed)

# 2) fit the bracket to clear the block with ≥2 mm of room
make fit SOURCE=runs/run_0000 CLEAR=2
#   or, full form:
#   caliper fit runs/run_0000 --ref obstacle=examples/obstacle.stl --min-clearance 2
```
Expect: `free dimension: bolt_circle ∈ [18, 90] mm`, the loop runs, and **ALL PASS** with the bracket
shrunk from 60 mm to ~39 mm and `obstacle_clearance  min_clearance(obstacle) >= 2.0  actual=3`. A new
`runs/run_0001/part.stl` is written — open both STLs in a viewer to see the bracket pulled back off the
block. Variants:
```bash
make fit SOURCE=runs/run_0000                       # default: just no collision (interference <= 0)
caliper fit runs/run_0000 --ref obstacle=examples/obstacle.stl --no-overlap --min-clearance 1
caliper fit runs/run_0000 --ref obstacle=my_part.stl --free wall   # vary a different parameter
```
**Notes:** the reference can be any STL (a motor, a rail, an enclosure). `fit` promotes a size
parameter to tunable so there's room to resize; pick which one with `--free`. Webapp fit UI (upload +
fit in the browser) is a logged follow-up — for now fit is CLI.
