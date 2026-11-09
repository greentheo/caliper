### 2026-10-30 · CALI-71 (#32) · Lighten the walls where the wood isn't working, in cuts a jigsaw can make
- **Theo:** "proceed to 32, 2 and 4", after the interface spec (`specs/caliper-four-questions-spec.md`, PR #34).
- **`lighten.py`:** the panels the loads pass *through* (not the one a load lands on face-on, which stays solid
  and keeps its plate check) are rastered at the voxel size, each cell a column through the plywood. Step by
  step (25/50/75/100% of each panel's inside), the quietest columns of what's left, by the strength check's
  own FEA across every load, come out; the result is cleaned into holes a jigsaw can cut (1.5 in solid rim
  where it's glued and screwed, no hole or web under 1.5 in, smoothed both ways and rounded to 1/2 in,
  clipped inside the rim), the voxels under those exact holes are removed, and the part is re-analysed. It
  stops at the first station that doesn't hold. `load_study` is split into `prepare()` + `check_load()` so
  both studies judge the same way.
- **`HOLES` (holes.py):** adopting a station writes the holes into the script as data; the sandbox cuts them
  after `build()` and gives them to the named pieces, so the take-off (area, weight, paint), the consistency
  check (samples skip holes, volume subtracts them) and later revisions all see them. The reference documents
  it; the designer is told to keep it. The CNC cut plan says the holes aren't on its sheets yet.
- **Live, on the stool (v3, study only — not adopted):** 49 s, 4 walls: 11% (2 holes, 0.7 lb) → 14% → 31% →
  **49% of the walls, 4 rounded windows, 3.3 lb lighter, still 3.1x** (the top's plate check governs
  throughout; the walls' FEA safety goes 10.9 → 4.9). On a scratch copy, adopting it: 6.9 L → 4.3 L of
  plywood, 8.9 → 5.5 lb, watertight, all four consistency checks pass.
- **The UI:** *Make it lighter* under *Will it hold?* — run it, click a step to see it in place, **Cut these
  holes**. The thickness table's **Use** asks the designer for that plywood, through the chat.
- **The build book** gets a *Will it hold?* page: each load, its safety, where it should break, and a blank
  for where it did (#10's sandbag test).
- Tests: `test_lighten.py` (4: holes cut, weighed and consistent; merge; the walls lighten, the top doesn't,
  every hole keeps its rim; adopting cuts them and a second study starts from them) and the book's
  breaking load in `test_release.py`. **Full suite: 478 passed.**
- Commit: `e431f44`, PR #35 (stacked on #33).
