### 2026-11-07 · Theo's bar stool, as its cards should read it (CALI-122 #137)
1. Open the bar stool (a copy) and press **Check it holds** on v7. *Will it work?* leads with "✗ Breaks its rule
   shell_wall_thickness: its walls are 0.25 mm around z 16.1 in; it says at least 2.85 mm", and *Rules on this part*
   marks each rule with its verdict.
2. The strength line says where its worst stress is ("in the cone skirt around z 15.3 in, among 7/32 in walls the
   voxels can't see"), and gives the seat its own number by hand: "as a round plate on its 10.6 in ring: 3.3 times
   over". Nothing says "seat top" for a hot spot in the cone.
3. **Carve it** and **Lighten it** are off: "its check says it fails (0.5 times over, a coarse run: the fail may be
   the model's; …): make it hold first, then carve".
4. The weight goal reads "13.1 lb, over its 10 lb cap"; the Score panel says "(cap 10 lb)".
5. Start a carve on a part that holds: its panel says "· running for N min" from the start.
6. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_preflight_bar_stool.py`.
