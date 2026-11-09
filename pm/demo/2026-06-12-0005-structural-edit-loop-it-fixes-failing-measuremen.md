### 2026-06-12 · Structural-edit loop — it fixes failing measurements now (CLI + browser)
**New:** `caliper gen` (and the webapp) don't just author a part once — they **iterate**. When the
built part fails a measured check, the LLM is handed the failing assertion (value + margin) and revises
the script, until it's green or it gives up (honestly — it reports "best effort", it won't fake a pass).
**Try it — CLI:**
```bash
make gen INTENT="a hexagonal pen cup, 70mm tall, 60mm across the flats, 3mm walls, closed bottom"
# watch the header: "after N round(s) (X build-error heal(s), Y revision(s))"
cat runs/run_00NN/part.py     # the CadQuery it wrote/revised
```
**Try it — browser:**
```bash
make serve     # Chrome/Edge → http://127.0.0.1:8000
```
Tick **“✦ author any part”** (the Build button becomes **Author ▶**), type any part — e.g.
*"a round coaster, 90mm diameter, 4mm thick, with a 3mm raised lip"* — and hit Author. It renders the
result in 3D and shows the authored **part.py** in an "Authored script" panel. (Authoring is slower than
the bracket path — LLM + multiple build rounds, ~30–60s.) Loading an authored part from **Recent parts**
shows its script too.
