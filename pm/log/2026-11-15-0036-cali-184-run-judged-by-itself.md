### 2026-11-15 · CALI-184 (#295) · #303 re-check: a Lighten run is judged by itself

The foreman's one line on #303.
- **What was wrong:** `lighten.wrong_material` asked `made_of` of the part as it is now.
- **Now it judges the run by itself:** a Lighten run whose material is a print ran as a sheet part's trim, whatever the part has become since.
- **The sheet's name** comes from the run's own `sheet`, else from what its panels are (the pieces they name, where the part still has them as sheets), else "its sheets".
- **Pinned:** the part made all printed after the run is still "Not trusted: it ran as PLA (printed), not as its sheets. Lighten it again.", and still refuses adoption. A run that names its sheet is said by it. A carve's own material isn't judged here.
- **Mutants:** 3, all caught: the run's sheet ignored, the panels ignored, and judged by the part again.
- **Around run:** 38 files pass, every test that touches Lighten.
