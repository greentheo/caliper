### 2026-11-10 · CALI-149 (#202) · A carve with nothing to go by says so

A real carve of a bracket failed with `float division by zero`. Its load goes straight down through the foot into the floor that holds it, so the strength check reads no stress at all, and whittle divides by the peak stress. Carve now refuses in words, from the same test the card and the button read, and a step of a sweep that reads no stress is said the same way. Tests: tests/test_carve_no_stress.py, real FEA on the bracket. The whole suite is CI's.

From the review: it's refused only when no case read stress, and the words give both things to look at. A check that saw almost no stress isn't "Holds": a case whose peak is under 1% of the load's own stress (force over footprint) reads as not resolved, through the verdict layer. Across 60 stored runs the lowest real ratio was 1.3, and only this bracket read as blind.
