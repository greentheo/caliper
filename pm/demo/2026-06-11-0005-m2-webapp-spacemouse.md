### 2026-06-11 · M2 — webapp + SpaceMouse
**New:** `make serve` → 3D webapp (FastAPI + three.js). Build, refine, view, download in the browser;
3Dconnexion SpaceMouse via WebHID. **Try:**
```bash
make serve
# open http://127.0.0.1:8000 → Build it → Refine "make the holes 8mm and add a rib" → ⬇ STL
# SpaceMouse: click "Connect SpaceMouse" (Chrome/Edge), pick the device, push/twist to fly the model
```
