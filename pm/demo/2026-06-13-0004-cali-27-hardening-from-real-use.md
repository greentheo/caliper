### 2026-06-13 · Hardening from real use (CALI-27)
**Fixed** (from Theo's reports): the **partial-machine bug** — one failed/slow part used to abort the
assembly load and strand a half-rendered machine; parts now load in parallel, the viewer renders what
worked, and the error bar **names the broken part with its actual exception**. Plus a **"❓ How this
works"** primer in the left panel (what to click, which actions need the API key), step-by-step Insert
hints, and a README **"▶ Run it"** block: `make serve` → **http://127.0.0.1:8000** (local only — it's
not hosted anywhere). Try it: load `corner-leg` in Assemblies — 4/4 parts, ALL PASS.
