### 2026-06-11 · M1 — refinement loop
**New:** `caliper refine` / `make refine`. Apply a plain-English change to a prior run and re-run.
**Try:**
```bash
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"
make refine SOURCE=runs/run_0000 INSTRUCTION="make the holes 8mm"
# verify it changed: the new report shows bolt_pattern diameter=8.0, and runs/run_0001/part.stl differs
```
Recognized tweaks: hole size (`"8mm holes"`, `"M6 holes"`), hole count (`"6 holes"`, `"one hole per
side"`, `"three holes per leg"`), bolt spacing (`"bigger spacing"`, `"spacing 75mm"`), wall
(`"thicker walls"`, `"wall 4.5mm"`), cable bore, ribs. Free-form edits → use the LLM path (drop `--no-llm`).
