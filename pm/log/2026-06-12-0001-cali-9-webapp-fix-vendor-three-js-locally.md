### 2026-06-12 · CALI-9 · webapp fix — vendor three.js locally (no CDN)
- Bug (real-use): on Theo's machine the Build button did nothing + a 404 in devtools. Cause: three.js
  was imported from the **unpkg CDN**; when that's blocked/offline/flaky the module import fails and
  `app.js` never finishes loading, so no event handlers attach. (Worked in the test browser where the
  CDN resolved — hence missed.)
- Fix: **vendor three.js locally** (`web/static/vendor/three/` — three.module.js + OrbitControls +
  STLLoader) and point the import map at local paths. App is now self-contained and works offline.
- Also: `<link rel="icon" href="data:,">` to kill the noisy favicon 404; an on-page error bar that
  shows load/runtime errors (so a dead button is never silent again); recursive package-data glob.
- Verified in-browser: zero external requests (all `localhost`), build → ALL PASS + render. 71 passed.
- Commit: 95a2e4a
