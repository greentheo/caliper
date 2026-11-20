### 2026-11-19 · CALI-203 (#335) · Lighten judges and weighs each panel in its own material

Lighten used the sheets' material, their most by volume, for everything it did to a panel:
- the allowable of a holed panel;
- the allowable at a picture's edge;
- the allowable of the top's holes;
- what every hole and every thinner sheet weighs.

In a part of XPS walls with a plywood floor, the floor's holes were held to foam's strength and weighed as foam. Since
#328 the plate check reads each sheet in its own material; Lighten didn't.

**The fix** (`lighten.py`):
- `own_of(ctx, name, mat)`: a panel's own sheet material (`L.own_material`), or `mat` where it has none.
- `allow_of(m)`: strength × across (plywood's half across its face).
- `saved_grams`: each panel's holes at its own density.

`judge_holed` (the strength check's holed panels and pictured walls), Lighten's top holes, each step's saved weight and
the thinner-sheet weights all go through them.

**Pinned** (`tests/test_lighten_own_material.py`): #328's box on two rails, 2 in XPS walls, a 3/4 in plywood floor and a
plywood left wall, 10 lb on the floor.
- each piece's own material, and the two helpers;
- the holes weigh what their own panels are made of;
- the strength check judges the holed floor and the plywood wall's picture edge each in plywood. The case holds: on
  main the hole read ✗ 0.24, judged in foam;
- Lighten holes the plywood floor by plywood, and weighs every step and every thinner sheet panel by panel.

On main, Lighten stopped at its first top step (✗ 1.2). Now it takes 22 top holes and holds at 2.25 or more.

**Fail first:** all four failed on main.

**On top of #353** (#348, the FEA in each piece's own material, on review): all four pass there too. The third first
pinned the case's number to the FEA's (2.39 here). Under #353 the foam walls' buckling governs instead (16.88), so that
test was wrong: it pinned main's governing check, not the claim. It now asserts the case holds at 2 or more, which is
what the bug broke.

**Mutants** (each anchor once, scratch copy, before merging main; main's change near them, #350's `L.solve`, doesn't
touch their lines), all 7 caught:
1. the holed panel at the sheets' material;
2. the picture edge at the sheets' material;
3. the top holes at the sheets' material;
4. the holes weighed at the sheets' density;
5. the thinner sheet weighed at the sheets' density;
6. `own_of` always the sheets';
7. `allow_of` without plywood's across.

**Theo's designs:** no studied part mixes sheet materials (#353's around runs). The cargo box does, but it has no
`loads()`, so Lighten has nothing to change there today.

Main merged at cfbe694 (no conflict).
