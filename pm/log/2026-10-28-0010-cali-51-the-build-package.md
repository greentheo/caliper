### 2026-10-28 · CALI-51 · The build package
- **Theo:** "build it! and relaunch the server, I need to take some screenshots to show a friend".
- **`release.py`:** `make()` → `releases/<NNN>/` — cut plans and scorecard brought current, then the build
  book (HTML; PDF via headless Chrome, own temp profile), `plasma/`, `router/`, `assembly/` (a PNG per step),
  `cutlist.txt`, `shopping.txt/.csv`, `scorecard.json`, `source/`, zip. Assembly order from the layers
  `construction._layer` already sorts pieces into, parts bottom-up, then skin, mount, finish.
- **Drawings:** first as painter's-sorted SVG — big faces covered what's in front of them, and coplanar
  patches z-fought even after subdividing; now a small numpy depth-buffer rasteriser (fan triangles, plates
  even-odd with plane depth, outlines depth-tested, 2× supersampled) writing PNG with zlib only.
- **Bug found — mirrored panels inside out:** the right-hand bands are the left's mirror, so their winding
  (and normals) flipped; unfold-to-sheets read every right-side seam as 180° − its angle (bevel 50–71° vs
  19–40° on the left) and couldn't tell inside from outside (128 mountain / 128 valley). `panels_obj` now
  winds every face away from the part's middle: 233 mountain / 23 valley, bevels symmetric. Same 4 XPS
  sheets at 59%. Cut plan re-run for cargo_box v14.
- **Bug found — the server crash:** four concurrent `GET /api/designs/<slug>` killed it (SIGABRT; SIGSEGV
  when two tabs loaded together) — OCCT from FastAPI's thread pool. `occt.OCCT` (an RLock) now wraps
  `DesignStore.evaluate`, `part_geometry`, the sandbox's STEP import and promote's part load. 12 concurrent
  design loads + STL fetches: all 200, server up.
- **Camper release 001:** frame v26, cargo_box v14; ready to cut (11/11); 11 steps; 5 sheets; ~$566 to buy
  (rounded up to what's sold; the scorecard's $451 is what's used). Shopping: 6 ft 2x2x1/8, 14 ft 1x1x1/16,
  a 19 × 18 in piece of 1/8 plate, 1 ply + 4 XPS, 5 1x2 + 3 2x2, 8 yd cloth, ½ gal epoxy, 3 qt paint, two
  jacks rated 500 lb+.
- Tests: `test_release.py` (8), `test_cutplan.py` +1. Full suite green (447 passed).
- Commit: `3170a12`
