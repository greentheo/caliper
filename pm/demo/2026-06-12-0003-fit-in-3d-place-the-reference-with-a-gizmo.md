### 2026-06-12 · Fit in 3D — place the reference with a gizmo (webapp)
**New:** the webapp can now do fit-to-reference, with the reference **positioned in 3D** (you asked the
right question — fit needs the reference *placed* relative to the part, not just baked coordinates).
**Try:**
```bash
make serve     # → http://127.0.0.1:8000  (Chrome/Edge)
```
1. Type an intent → **Build it ▶** (e.g. the 60 mm bracket).
2. Open **“Fit to a reference (M3)”** (left panel) → **choose an STL** (any part: a motor, a rail, or
   `examples/obstacle.stl`). It appears **orange & semi-transparent** with a move/rotate **gizmo**.
3. **Drag** it (or press **E** to rotate) so it sits where it should mate against the part.
4. Set **clearance** (mm) and/or leave **no collision** ticked → **Fit ▶**. Caliper resizes the part to
   clear it and re-renders. The part is shown in its real build frame, so *what you place is what's
   measured*. The fitted part lands in **Recent parts**; reloading it re-draws the reference where you
   put it.
**Notes:** the part stays fixed at the origin (the datum) — you move the reference; only the relative
pose matters. **Heads-up:** a fit against a *complex* reference can take ~30 s (it runs many exact mesh
booleans); a simple block is a few seconds. CLI `caliper fit` is the scriptable equivalent (below).
