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
- ⏳ **Next (M2):** a web UI (FastAPI + React/three.js) — intent box, live spec editor, 3D viewer,
  report panel, STL download. Until then everything is CLI.

**Part family so far:** corner brackets for T-slot extrusion (e.g. 2020). One body, bolt holes on
each flange, optional cable bore + stiffening ribs.

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

## 📓 Demo log (newest first)

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
