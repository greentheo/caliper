### 2026-06-13 · A whole small machine — a corner leg with measured bolt alignment (CALI-25/23/26)
**New:** Caliper now measures a **multi-part machine**, including whether the **bolt holes line up**.
The demo `examples/machine.yaml` is a corner leg: two solid **20×40 mm bars** (post + beam) at a right
angle, a **gusset bracket**, and a **foot**, screwed with M5s through aligned holes.
```bash
caliper assemble examples/machine.yaml
# → ALL PASS: 4 touch mates, nothing_collides, and three hole-alignment checks at ~0mm:
#     hole_misalignment(corner_bracket, bar_v) <= 0.5   ✓
#     hole_misalignment(corner_bracket, bar_h) <= 0.5   ✓
#     hole_misalignment(foot, bar_v) <= 0.5             ✓
```
Each part is a CadQuery script built at assemble time (CALI-23, B-rep kept → exact hole probes). The new
`hole_misalignment(a, b)` probe detects each part's holes, poses them into the assembly frame, and
returns the smallest axis offset between a near-parallel pair (0 = a screw passes straight through both).
In the **webapp** (Assemblies → corner-leg) the parts render with the bracket's bolt holes visible, and
any colliding pair is shaded **red** (CALI-26). To see the measurement bite: nudge a hole's coordinate
in one of `examples/machine/*.py` and re-assemble → the matching `*_bolts_align` check fails.
**See `TESTING.md` for the full hands-on walkthrough of everything built so far.**
