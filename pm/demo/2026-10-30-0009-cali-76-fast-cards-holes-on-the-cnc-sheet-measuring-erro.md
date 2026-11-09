### 2026-10-30 · Fast cards, holes on the CNC sheet, measuring error (CALI-76 #44, CALI-77 #45, CALI-68 #28)
1. Click the stool: its four cards come up in about a second (they took 6–11 s).
2. Lighten the stool and cut a step in, then **How do I make it? → the numbers → Cut plan → Make the cut plan**:
   the sheet SVG/DXF has the holes inside each panel, square to the sheet. Needs unfold-to-sheets at `8fc66c9`
   (`make tools`; your own checkout: merge greentheo/unfold-to-sheets#2 and pull).
3. Say "the walls must be at least 19.05 mm" on a 3/4 in plywood part: the offer is
   `min_wall >= 19.05 - 0.15` and says the 0.15 mm is what measuring a wall can be off by; it holds.
4. Offline: `python -m pytest tests/test_answers.py tests/test_cutplan.py tests/test_promote.py`.
