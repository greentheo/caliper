### 2026-06-11 · refine parser — per-side & word-number hole counts
**New:** the offline refiner now understands singular "hole", word-numbers ("one"…"ten"), and
**per-flange** phrasing ("on each side", "per leg"). A single hole per flange is centered by
construction. **Try:**
```bash
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"
make refine SOURCE=runs/run_0000 INSTRUCTION="only do one hole on each side, in the middle"
# → hole count 4 → 2 (1 per side), centred; report shows bolt_pattern count=2
make refine SOURCE=runs/run_0000 INSTRUCTION="put three holes per leg"   # → 6 total
```
