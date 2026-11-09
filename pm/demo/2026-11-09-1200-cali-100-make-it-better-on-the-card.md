### 2026-11-09 · Make it better on the card (CALI-100 #92, the server side)
1. On a printed part that holds, *Will it work?* ends "Carve the … where it isn't working, to use less filament: it
   takes at least about N min at this size." Click it: it goes to the panel with **Carve it**.
2. After a carve, the line gives the result ("61% of the printed part carved away, 644 g less filament, still about
   2.6 times over").
3. On a sheet part, a thinner sheet the plate check still passes comes first, then Lighten. On a part that fails as
   drawn, only a thicker sheet that would make it hold.
4. On Studies, a printed part lists **Carve**, and Lighten says "it has no sheet pieces: a printed part is carved".
5. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_make_it_better.py`.
