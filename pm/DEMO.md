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
  measurement report, refine box, STL download, a **Recent parts** list (click to reload past parts for
  viewing/editing), and **3Dconnexion SpaceMouse** support (WebHID). "Jam in 3D space."
- ✅ **M3 — fit to reference.** Import an existing part as an STL (`role: fixed`) and Caliper resizes
  your part until it **fits** it — measuring overlap (`interference`) and the gap (`min_clearance`)
  exactly, then shrinking *just enough* to clear with the clearance you ask for. Available in the
  **CLI** (`caliper fit` / `make fit`) **and the webapp**: drop in an STL, **drag/rotate it into place**
  with a 3D gizmo, hit Fit. The pose you set in 3D is exactly what's measured. "Make it fit *this*."

- ✅ **LLM-authored generator (any part).** `caliper gen "<intent>"` — the LLM **writes the CadQuery
  script** (not just a bracket), runs it sandboxed, measures it, and **self-heals build errors** from
  the traceback. The spec's primary generation strategy: loose idea → real geometry, no hand-coded
  family. The authored script is saved as `part.py` (the editable source of truth).
- ✅ **Assembly model (CALI-20).** `caliper assemble <file>` — represent **N parts + named mates +
  assembly-level assertions** and measure them. Each mate (`touch`/`clearance`/`fit`/`no_interference`)
  between two posed parts is a measured fit; `max_interference() <= 0` proves no pair collides. The
  first step from "a part" to "a machine." (Webapp viewer is CALI-20b.)

**Two generators now:** the **hardcoded bracket** (`run`/`refine`/`fit` — fast, offline-capable, the
optimizer loop) and the **LLM author** (`gen` — arbitrary parts, needs `ANTHROPIC_API_KEY`).
**Bracket family:** corner brackets for T-slot extrusion (2020…), bolt holes per flange, optional cable
bore + ribs. **Bracket limits:** 90° only (CALI-11), through-holes only (CALI-12) — these need bracket
generator work. The **LLM author** sidesteps those (it writes whatever geometry the intent describes)
and now **iterates to fix failing measurements** too (CALI-17), not just build errors — in the CLI
(`gen`) and the webapp ("✦ author any part").

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
make test          # expect: 121 passed
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

### 2026-06-12 · Assembly model — a collection of parts that fit together (CALI-20)
**New:** Caliper now represents **N parts + named mates + assembly-level assertions** and *measures*
them. Each mate (`touch` / `clearance` / `fit` / `no_interference`) between two parts becomes a measured
check — "these two seat flush", "this slips into that at a slip fit" — and `max_interference() <= 0`
proves no pair collides. This is the first step toward the north star ("insert a support between the
wheel and the XYZ assembly"): the geometry of a *machine*, not just one part.
**Try it — CLI:**
```bash
python examples/make_assembly.py          # (re)generate base/post/cap STLs (centered, local origin)
make assemble                             # measures examples/assembly.yaml → ALL PASS
#   caliper assemble examples/assembly.yaml
# → base→post→cap stack; two `touch` mates (clearance ≈ 0.000) + nothing_collides → ALL PASS.
#   Parts are posed by `position:` in the YAML; the fit probes measure them where they sit.
```
The assembly file (`examples/assembly.yaml`): `parts` (id + source STL/run-dir + position/rotation),
`mates` (between two part ids, a kind), and free-form `assert`. Bump a part's `position` so two boxes
overlap → the mate **and** `nothing_collides` both flip to `fail` with the overlap volume as the actual.

### 2026-06-12 · Fits & tolerances — target a fit class, stop fighting noise
**New:** ask for a **fit** (press / snug / slip / free / running) and Caliper tunes the part until the
clearance lands in that band — "fits" as a first-class idea, not a magic number. Plus tolerant
assertion helpers (`approx`, `within`, `fits`) so a 0.01 mm measurement wobble no longer fails a check.
**Try it — CLI:**
```bash
make run INTENT="a 60 mm corner bracket for 2020 with four M5 holes"      # → runs/run_00NN
caliper fit runs/run_00NN --ref obstacle=examples/obstacle.stl --fit slip
# → constraint "0.12 <= min_clearance(obstacle) <= 0.3"; the bracket resizes (60 → ~41.8mm)
#   until clearance ≈ 0.19mm — centre of the slip band. Try --fit press / free / running too.
```
**Try it — browser:** `make serve` → build a bracket → open **“Fit to a reference (M3)”** → import an
STL, place it → pick a **fit** class from the dropdown → **Fit ▶**.
**Also:** fitting/refining an **LLM-authored** part now shows a clear message instead of silently
rebuilding a bracket (the bug from before) — full author-loop fit is tracked (CALI-22).

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

### 2026-06-12 · LLM-authored generator — `caliper gen` (any part)
**New:** the LLM writes the CadQuery script itself, so you're no longer limited to the bracket family.
It runs the script **sandboxed**, measures it, and **self-heals build errors** (feeds the traceback
back and retries). **Try (needs `ANTHROPIC_API_KEY`):**
```bash
make gen INTENT="a cylindrical desk cable grommet: 40mm outer diameter, 30mm inner bore, 25mm tall, with a 5mm flange lip at the top"
# or non-bracket things like:
make gen INTENT="a phone stand for an 8mm-thick phone, angled back 65 degrees"
make gen INTENT="a 60mm-tall hexagonal pen cup with 3mm walls"
```
Expect: a drafted spec (the LLM also asks good clarifying questions), then **"✓ built on attempt N"**,
a measurement report, and a run dir with **`part.py`** (the script it wrote — open it, it's real
readable CadQuery) + `part.stl`. The grommet test produced a clean hollow tube + flange union, 7/8
asserts passing. **Note:** today it self-heals *build* errors but doesn't yet iterate to fix failing
*measurements* (that's CALI-17). The bracket path (`run`/`refine`/`fit`) is unchanged.
> **Also fixed:** LLM intake/refine were silently falling back to the offline bracket on your model
> (`claude-sonnet-4-6`) — an assistant-prefill the model rejects, plus schema mismatches. So
> `make run-llm` / `make refine-llm` now actually use Claude too, not just `gen`.

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

### 2026-06-12 · M3 — fit a part to an imported reference (CALI-10)
**New:** `caliper fit` takes a part you already made and an imported STL, and resizes the part until it
clears that reference. Two checks are measured exactly on the meshes: `interference` (overlap volume,
0 = no collision) and `min_clearance` (smallest gap, negative if they interpenetrate). The optimizer
shrinks the part **snugly** — just enough to clear, not down to a stub.

**Try it (needs cadquery env):**
```bash
# 1) make a part to fit, and the demo obstacle (a block parked against the bracket's flange end)
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"   # → runs/run_0000
python examples/make_obstacle.py        # writes examples/obstacle.stl (already committed)

# 2) fit the bracket to clear the block with ≥2 mm of room
make fit SOURCE=runs/run_0000 CLEAR=2
#   or, full form:
#   caliper fit runs/run_0000 --ref obstacle=examples/obstacle.stl --min-clearance 2
```
Expect: `free dimension: bolt_circle ∈ [18, 90] mm`, the loop runs, and **ALL PASS** with the bracket
shrunk from 60 mm to ~39 mm and `obstacle_clearance  min_clearance(obstacle) >= 2.0  actual=3`. A new
`runs/run_0001/part.stl` is written — open both STLs in a viewer to see the bracket pulled back off the
block. Variants:
```bash
make fit SOURCE=runs/run_0000                       # default: just no collision (interference <= 0)
caliper fit runs/run_0000 --ref obstacle=examples/obstacle.stl --no-overlap --min-clearance 1
caliper fit runs/run_0000 --ref obstacle=my_part.stl --free wall   # vary a different parameter
```
**Notes:** the reference can be any STL (a motor, a rail, an enclosure). `fit` promotes a size
parameter to tunable so there's room to resize; pick which one with `--free`. Webapp fit UI (upload +
fit in the browser) is a logged follow-up — for now fit is CLI.

### 2026-06-12 · Recent parts (browse/load) + hole-count hang fix
**New:** a "Recent parts" panel in the webapp — every run is listed (newest first, with its label +
timestamp); click one to load its spec, report, and 3D mesh; refine from there forks a new part.
**Fixed:** an intent like "…for 2020 with two M6 holes" used to hang (it read the extrusion size 2020
as the hole count → drilling 2020 holes). Now parsed correctly + clamped. **Try:**
```bash
make serve   # build a few parts, then click between them in "Recent parts" on the left
```

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
