### 2026-06-13 · Viewer UX — resize, panning, fit-to-view (CALI-21c)
**Fixed** (from real use on a second monitor): the 3D view now **resizes correctly across monitors/DPI**
(canvas always fills the panel, crisp at any pixel ratio); **middle-mouse (wheel-press) drag pans**
(CAD-style: left = orbit, middle/right = pan, scroll = zoom); and a **⤢ fit** button (or the `F` key)
**recenters** the view with the **ground grid sized to the content**. Just `make serve` and drag with the
wheel button, or hit `F` to refit after rotating away.
