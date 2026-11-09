### 2026-06-13 · CALI-21c · Viewer UX — monitor-resize, middle-mouse pan, fit-to-view + adaptive grid
- **Reported (Theo, after plugging into a different monitor):** the 3D view didn't resize correctly,
  no middle-mouse panning, and it needed a proper recenter / stage sizing.
- **Monitor/DPI resize:** `resize()` now re-applies `renderer.setPixelRatio(min(dpr, 2))` every time
  (moving monitors changes `devicePixelRatio`; the old code set it once at init → stale → blurry/
  mis-sized). CSS now sizes the canvas (`#viewer canvas { width/height: 100% !important }`) while
  three.js sets only the draw buffer — so the canvas always fills the panel and the buffer matches DPI.
  Added a `window 'resize'` listener + a `matchMedia('(resolution: …dppx)')` watcher (re-armed each
  change) to catch DPI-only changes that don't fire the ResizeObserver. Bonus: this removes the benign
  `ResizeObserver loop` warning at its source (no more inline-style feedback).
- **Panning:** OrbitControls remapped CAD-style — `mouseButtons = {LEFT: ROTATE, MIDDLE: PAN, RIGHT:
  PAN}`, `screenSpacePanning = true` (was MIDDLE: dolly). Wheel-press-drag now pans. Pick-to-select
  guarded to **left button only** so a middle/right drag pans without selecting a part.
- **Recenter + adaptive stage:** a **⤢ fit** button (and `F` key) reframes whatever's on screen
  (`frameScene`/`frameAssembly` refactored onto a shared `frameBox(contentBox())`). The ground grid is
  now **sized to the content** (`fitGrid` — rounds up to 20 mm, floor 40 mm, positioned under the
  content) instead of a fixed 400 mm plane that dwarfed small parts.
- **Verified live in-browser (Preview MCP):** canvas fills the viewer and the buffer matches DPR
  (`bufferMatchesDpr: true`); resizing the viewport 1280→1100px re-fills correctly; loading two-posts +
  ⤢ fit recenters with a content-sized grid; zero console warnings/errors. Web-only change (no Python) —
  full suite still **153 passed**.
  Commit: c4aec8c
