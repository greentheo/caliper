### 2026-06-13 · CALI-21b + CALI-20b · Webapp insert UI + assembly viewer — VERIFIED LIVE
- **What it is:** the CALI-21 headline, now **clickable in the browser**. Load an assembly, see all its
  parts in 3D, **click two parts to pick the interfaces**, choose a fit + intent, hit Insert → the LLM
  authors the bridging part, it drops into the scene (green), and the whole assembly is re-measured.
- **Backend (`server.py`):** `GET /api/assemblies` (lists every YAML under `CALIPER_ASSEMBLIES`, default
  `examples/`, that parses as an Assembly), `GET /api/assembly/{id}` (parts + poses + stl_urls + measured
  report), `GET /api/assembly/{id}/part/{pid}.stl` (serves a posed part's STL), `POST /api/insert`
  (wraps `insert.insert_part` → persists the authored part as a run → `add_part_to_assembly` → saves
  `<id>.inserted.yaml` → re-measures → returns the new part's stl_url + report + script + bridge info).
- **Frontend (`app.js`/`index.html`/`style.css`):** an Assemblies list; multi-part rendering (each part
  posed, colored by role — gray=fixed, blue=movable, **green=inserted**); **click-to-pick** via raycast
  (drag vs click disambiguated by pointer travel) with emissive highlight + a picks readout; an insert
  panel (intent / id / fit); the assembly report reuses `renderReport`. `window.__asm` debug seam
  (mirrors `__caliperSM`). Benign `ResizeObserver loop` warning filtered from the error bar.
- **Bug found & fixed (live):** `insert_spec` resolved a part `source` against `base_dir`, then
  `improve`→`load_references` re-resolved the *relative* result against `ref_base` → doubled the dir
  (`examples/examples/post.stl`). The CLI dodged it (it passed an absolute base_dir); the server's
  relative `examples` exposed it. Fix: `insert_spec` stores **absolute** reference paths.
- **VERIFIED LIVE in the browser (Preview MCP, real Claude API):** loaded `two-posts`, both posts render
  at x=±30; picked both (highlight + button enable confirmed); Insert → LLM authored the cross-bar in
  **1 round**, rendered green between the posts; report ALL PASS (both mates **0.21 mm**, nothing
  collides); saved as `insert_demo.inserted`. No console errors.
- Tests: `test_server.py` +5 — list/get assembly + serve part STL + insert route-through (faked author)
  + bad-between 400 + unknown-assembly 404. **153 passed.**
- **Deferred:** in-browser assembly *authoring* (build parts from intent at insert time) → CALI-23;
  per-part red/green collision shading → polish (the report already shows per-mate pass/fail).
  Commit: 914a791
