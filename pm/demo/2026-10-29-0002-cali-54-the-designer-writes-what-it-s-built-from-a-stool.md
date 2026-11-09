### 2026-10-29 · The designer writes what it's built from: a stool from one sentence to a cut sheet (CALI-54, #1)
1. `make serve`, then **+ New design**: *"A step stool so my 6-year-old can reach the bathroom sink. Made
   from 3/4 in plywood, glued and screwed. It has to hold me too (200 lb)."* → **Use these answers**.
2. Say **build the stool**. The part comes back with a weight under **Built from** (no script written by
   hand): its panels by name, one 4x8 sheet of plywood, paint.
3. Click the stool → **Make the cut plan**: one sheet, the panels nested and labelled (DXF, SVG, PDF).
4. To see the check bite, move one panel in the part's `construction()` (add 300 to a y) and ask for any
   change: it takes an extra round, because the first fails `construction_inside`, naming the panel and how
   far out it is, and the designer puts it back. `python -m pytest tests/test_consistency.py` runs the same
   cases offline.
