### 2026-11-11 · CALI-92 (#70) · the strength and measurement items, reworked

PR #228, after the review of f544aa7.

- **Rule 6, item 6.** A carve step that cut under a held edge lost the plate check and fell back to the FEA, which reads a
  plywood top high: the review's notch on the mixed stool went 0.57 → 1.66. Every step's number now has the as-drawn
  plate number as its ceiling (`check_load` reads `ctx["plate_ceiling"]`, which the carve fills at step 0). A capped case
  carries the as-drawn plate with `as_drawn`, and the carve's notes say why. Pinned on the review's notch and on a whole
  side cut away. A capped step's plywood governs, so #221's `span` doesn't fire on it.
- **Item 2.** The falloff beside the foot is now Navier's series for a plate held all round. The sample top gives 0.776
  along the long side and 0.594 along the short, as the review found. Held all round, the card says to lay the
  straightedge on the two long edges and read toward a short end, and says what the other way reads (about 77% of it).
- **Item 17.** The comment's "a joined part read up to 0.07" didn't reproduce. An L, a T, walls at 30° and 45°, a wall on
  a plate, a tube on a plate and a ribbed box read 0.008 to 0.012 mm short at 0.8, 1.2 and 2 mm, so there's no 0.08
  floor. The comment now gives those numbers.
- **CI.** `got.within(room)` at `pictures.py:226`, which the spatial guard reads.
- **Mutants.** `spot` on the numbers, the half inch, `& ~wood` and buckling in the carve's notes are pinned.
- Main merged in (#221's `span` meets the carve and the trial card).

Left: `_held_edges` still probes only an edge's middle (older than this PR, noted by the review).
