# Caliper — demo & testing log

**What you can run today, and exactly how to try each thing that's shipped.**
Updated after every bit of work (it's part of the definition of done — see [`README.md`](README.md)).
Newest demos first.

---

## 🧭 Current capabilities (at a glance)

- ✅ **M0 — one-shot loop.** Type a plain-English part request → Caliper drafts a spec, asks a
  clarifying question, builds a real CadQuery corner bracket, measures it exactly (bbox, wall, holes,
  mass, watertight), grades it against the spec, and writes a downloadable **STL**.
- ✅ **M1 — refinement loop.** Take an existing part and a plain-English tweak ("make the holes 8 mm",
  "bigger spacing", "thicker walls", "add a rib") → it re-derives the spec, regenerates, re-measures,
  and writes a new STL. The optimizer also auto-tunes a continuous parameter when a numeric check fails.
- ✅ **M2 — webapp.** `make serve` → a browser UI: intent box, **3D viewer** (three.js), live
  measurement report, refine box, STL download, and **3Dconnexion SpaceMouse** support (WebHID).
  "Jam in 3D space."

**Part family so far:** corner brackets for T-slot extrusion (e.g. 2020). One body, bolt holes on
each flange, optional cable bore + stiffening ribs.
**Not yet (generator limits):** fixed **90° bend only** (no variable angle — CALI-11), plain
through-holes only (**no threads/tapped/insert holes** — CALI-12). The LLM can only set parameters
the generator can build, so these need generator work first, not just a better prompt.

---

## ⚙️ One-time setup

```bash
# Build the OCCT env (micromamba — Anaconda's classic solver stalls on cadquery; see pm/LOG.md)
curl -Ls https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xj -C /tmp bin/micromamba
/tmp/bin/micromamba create -p /opt/anaconda3/envs/caliper -c conda-forge -y python=3.11 cadquery
/opt/anaconda3/envs/caliper/bin/python -m pip install -r requirements-pip.txt
make install            # makes the `caliper` command available
```
> `make` targets resolve the env automatically — no `conda activate` needed.

**Optional — enable free-form (LLM) intake/refine** (the `--no-llm` paths need none of this):
```bash
cp .env.example .env        # then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```
The CLI auto-loads `.env` from the repo root (or cwd). Or export it for the session:
`export ANTHROPIC_API_KEY=sk-ant-...`. Override the model with `CALIPER_MODEL=...`; set
`CALIPER_DEBUG=1` to see why an LLM call fell back to offline. `.env` is gitignored.

Then drive the Claude path through `make` with the `*-llm` targets (or `LLM=1` on `run`/`refine`):
```bash
make run-llm    INTENT="a sturdy 80mm bracket for 3030 with countersunk M6 holes"
make refine-llm SOURCE=runs/run_0000 INSTRUCTION="round the outer corners and lighten it"
# equivalently:  make refine LLM=1 SOURCE=... INSTRUCTION=...
```

---

## ▶️ Try it (current build)

**1. Run the full loop — idea → measured part → STL:**
```bash
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"
```
Expect: a drafted spec, one clarifying question, then `status: passed` with a ✓ report
(bbox `[60,20,60]`, min_wall ~2.99, 4×Ø5.2 ✓, mass ~8 g, watertight) and `STL: runs/run_0000/part.stl`.

**2. Refine the part you just made:**
```bash
make refine SOURCE=runs/run_0000 INSTRUCTION="make the holes 8mm bigger spacing"
```
Expect: a `changes` list (e.g. `spacing 60 → 68 mm`), a fresh ALL-PASS report, and a new
`runs/run_0001/part.stl`. Try also: `"thicker walls"`, `"add a rib"`, `"M6 holes"`, `"bigger cable bore"`.

**3. Run the regression guard (the test suite):**
```bash
make test          # expect: 61 passed
```

**4. Inspect a run's artifacts** (everything is saved + diffable):
```bash
cat runs/run_0000/spec.yaml      # the spec it built from
cat runs/run_0000/report.txt     # the measurement report
# open runs/run_0000/part.stl in any slicer / mesh viewer
```

---

## 🌐 The webapp (M2)

```bash
make serve            # → http://127.0.0.1:8000  (or: caliper serve --port 8000)
```
In the browser: type an intent → **Build it ▶** → the bracket renders in 3D with the ALL-PASS report;
type a tweak in **Refine** → it regenerates in place; **⬇ STL** downloads the mesh.

**3Dconnexion SpaceMouse** (Chrome/Edge — WebHID; not Safari): click **Connect SpaceMouse**, pick the
device. A live readout (rpt id / bytes / axes / raw) shows in the viewer's top-right once data flows;
push/twist the cap to pan/dolly/rotate. Mouse-orbit is always the fallback.
- **macOS gotcha:** the 3Dconnexion **3DxWare** driver usually holds the device, so WebHID opens it but
  sees no data → the app shows a red hint. **Quit 3DxWare** (menu-bar icon → Quit, or Activity Monitor →
  quit "3DconnexionHelper"), then click Connect again. (It's the same reason it can't run in the browser
  and Fusion at once.)
- **Tuning:** axis mapping/sensitivity are constants (`SM_GAIN_*`, `SM_SCALE`) at the top of the WebHID
  section in `web/static/app.js` — tweak if an axis feels reversed or too hot; the raw readout helps.
- **Driver / NL-Proxy mode (beta, CALI-14):** pick "Driver / NL-Proxy" in the dropdown to use the
  SpaceMouse *without quitting 3DxWare* (coexists with Fusion). It loads 3Dconnexion's proxy lib from
  `https://127.51.68.120:8181`. First time, **open that URL in a tab once to accept the driver's
  certificate**, then click Connect. Phase 1 connects + reports the API surface on-screen; full camera
  navigation (phase 2) is pending tuning against the on-screen telemetry — paste me what it shows.

## 📓 Demo log (newest first)

### 2026-06-11 · M2 — webapp + SpaceMouse
**New:** `make serve` → 3D webapp (FastAPI + three.js). Build, refine, view, download in the browser;
3Dconnexion SpaceMouse via WebHID. **Try:**
```bash
make serve
# open http://127.0.0.1:8000 → Build it → Refine "make the holes 8mm and add a rib" → ⬇ STL
# SpaceMouse: click "Connect SpaceMouse" (Chrome/Edge), pick the device, push/twist to fly the model
```

### 2026-06-11 · LLM path — robust JSON parsing
**Fixed:** `make refine-llm` failed with `JSONDecodeError` when Claude wrapped its reply in markdown.
The parser now strips code fences / prose and prefills `{` to force a clean object.
**Try (needs `ANTHROPIC_API_KEY`):**
```bash
make refine-llm SOURCE=runs/run_0000 INSTRUCTION="lighten it and round the outer corners"
# header should read "── changes (llm) ──"; if it says (offline), run CALIPER_DEBUG=1 make refine-llm ...
```
Note: the LLM can only set existing bracket params — variable bend angle (CALI-11) and threaded holes
(CALI-12) need generator work, not a prompt.

### 2026-06-11 · refine parser — per-side & word-number hole counts
**New:** the offline refiner now understands singular "hole", word-numbers ("one"…"ten"), and
**per-flange** phrasing ("on each side", "per leg"). A single hole per flange is centered by
construction. **Try:**
```bash
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"
make refine SOURCE=runs/run_0000 INSTRUCTION="only do one hole on each side, in the middle"
# → hole count 4 → 2 (1 per side), centred; report shows bolt_pattern count=2
make refine SOURCE=runs/run_0000 INSTRUCTION="put three holes per leg"   # → 6 total
```

### 2026-06-11 · M1 — refinement loop
**New:** `caliper refine` / `make refine`. Apply a plain-English change to a prior run and re-run.
**Try:**
```bash
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"
make refine SOURCE=runs/run_0000 INSTRUCTION="make the holes 8mm"
# verify it changed: the new report shows bolt_pattern diameter=8.0, and runs/run_0001/part.stl differs
```
Recognized tweaks: hole size (`"8mm holes"`, `"M6 holes"`), hole count (`"6 holes"`, `"one hole per
side"`, `"three holes per leg"`), bolt spacing (`"bigger spacing"`, `"spacing 75mm"`), wall
(`"thicker walls"`, `"wall 4.5mm"`), cable bore, ribs. Free-form edits → use the LLM path (drop `--no-llm`).

### 2026-06-11 · M0 — one-shot loop
**New:** `caliper run` / `make run`. Idea → spec → build → measure → report → STL, with the
ask-don't-assume clarify gate.
**Try:**
```bash
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes and a cable pass-through"
cat runs/run_0000/report.txt
```
Expect ALL PASS and a watertight bracket with four Ø5.2 holes and a Ø10 cable bore.
