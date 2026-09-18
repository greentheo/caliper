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
  viewing/editing), an **Assemblies** panel — load a multi-part assembly, **click two parts to pick
  interfaces, and Insert** a bridging part live (CALI-21b/20b) — and **3Dconnexion SpaceMouse** support
  (WebHID). "Jam in 3D space."
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
- ✅ **Insert-into-assembly (CALI-21) — the north-star headline.** `caliper insert <asm> --between a,b
  --fit slip` — the LLM **authors a new part that mates to two named interfaces** at a measured fit, in
  assembly coordinates, then it's added back and the whole assembly is re-measured. *"Insert a support
  between the wheel and the XYZ assembly."* Verified live (bridged a 50mm gap at 0.21mm/side, first try).
- ✅ **A whole small machine (CALI-25).** `caliper assemble examples/machine.yaml` — a 4-part corner leg
  (two solid 20×40 bars + gusset bracket + foot, M5s) measured green, **including bolt-hole alignment**
  (`hole_misalignment`). Parts build from CadQuery scripts at assemble time (CALI-23); the viewer shades
  collisions red (CALI-26). **See `TESTING.md` for the full testing walkthrough.**

- 🆕 **Talk to a design (CALI-29, M4).** `caliper chat <slug> "<message>" [--part ID]` — one
  conversational turn: it routes the message (Claude, or a deterministic parser offline), **revises the
  part you selected**, and **re-measures the whole design**, naming anything the change broke. Closes the
  real gap: until now there was *no way to refine a part that lives inside an assembly*. Say **"roll it
  back"** to undo. `--part` is what clicking a part in the viewer will do once CALI-32 lands.

- 🆕 **A Design — the container for what you're building (CALI-28, M4).** `caliper design new "..."`
  creates `designs/<slug>/`: the **root prompt**, the **requirements** clarified once (never re-asked),
  a **part tree**, and per part a **feedback history** plus a snapshot of **every revision**. It *is* an
  assembly underneath, so the whole engine (`assemble`, mates, `insert`) works on it unchanged — and a
  one-part design is just a one-part assembly. This is the spine of **M4: the design session**, where
  the UI becomes a viewport + a conversation instead of a control panel. See
  [`specs/caliper-conversational-spec.md`](../specs/caliper-conversational-spec.md).

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

## 🆕 CALI-29 — talk to a design; it tells you what your change broke

**What's new:** the conversation. One message, optionally scoped to a part, becomes a measured move —
and the reply names what the change broke **elsewhere in the design**, which is the whole point of
building this on top of a measurement engine.

This also closes a real gap: until now there was **no code path to refine a part inside an assembly**.
`refine` only worked on single-part runs; assembly members were static scripts with no revision path.

```bash
# seed a two-part design with a mate that must keep holding
python - <<'EOF'
from caliper.design import DesignStore
from caliper.assembly import Mate

box = ("def build(params):\n"
       "    import cadquery as cq\n"
       "    return cq.Workplane('XY').box({dx}, {dy}, 10).translate((0, {y}, 0))\n")

s = DesignStore.create("a 3D printer gantry, 300x300x400", slug="gantry")
s.add_requirement("rail type?", "MGN12 linear rail")
s.write_part("rail",     box.format(dx=200, dy=12, y=0),  intent="the MGN12 linear rail, 200mm long")
s.write_part("carriage", box.format(dx=40,  dy=20, y=40), intent="the X carriage that rides the rail")
s.assembly.mates.append(Mate(id="carriage_clears_rail", between=["carriage", "rail"],
                             kind="no_interference"))
s.save()
EOF
```

```bash
# 1. ask about it — no key needed, no geometry moves
caliper chat gantry "what parts exist?" --no-llm
```

```bash
# 2. change the part you'd have clicked  (needs ANTHROPIC_API_KEY)
caliper chat gantry "make it 60mm wide and give it four M3 mounting holes on the top face" --part carriage
```

```bash
# 3. now break something on purpose, and watch it get caught
caliper chat gantry "make it 120mm deep in the Y direction, keeping the same centre" --part carriage
```

```bash
# 4. undo
caliper chat gantry "roll it back" --part carriage
```

**What step 3 actually printed (live, real Claude call):**

```
  · routed → refine → carriage  (routed by Claude, via llm)
  · revising carriage…
  · carriage built in 1 round(s)
  · carriage → v3
  · measured the whole design

✗ revised **carriage** → v3 (1 round(s))
Every check on this part passes.

⚠ This change **broke 1 design check(s)** that passed before:
  • carriage_clears_rail: interference(carriage, rail) <= 0 → actual=7200.0 (margin -7.2e+03)
_Tell me how to fix it, or say **roll it back** to undo this revision._
```

Read that twice: **the part passes every one of its own checks.** It's the *design* that's broken, three
lines of conversation away from where you were looking. That's what re-measuring everything buys you.

And step 4:

```
↩ rolled **carriage** back to v2 (saved as v4)
✓ That fixed: carriage_clears_rail
The whole design measures green.
```

**Things worth poking at:**
- `cat designs/gantry/parts/carriage/part.py` after step 2 — it kept the world-coordinate
  `translate((0, 40, 0))` on its own. The revision is handed the design context (siblings, mates,
  enforced assertions, prior feedback) and told to build in the design's frame.
- `cat designs/gantry/log.jsonl` — every message and reply, with how it was routed.
- Try an ambiguous one: `caliper chat gantry "5mm wider please" --no-llm` — it **asks which part**
  instead of guessing. A wrong guess costs a whole authoring run.
- Try `--no-llm` on a change: routing goes offline, but *authoring* still needs the key.
- The rollback is itself a revision (`versions/` gains `v004`), so the undo is in the history, not a
  hole in it.

**What this does NOT do yet:**
- **No UI** — this is the CLI surface of the turn handler. Viewport + chat is **CALI-32**; `--part` is
  what clicking a part will do.
- **No streaming** — the turn blocks while Claude authors. The progress lines you see are the same
  events **CALI-31** will stream to the chat over SSE.
- **Feedback isn't promoted to assertions yet** (**CALI-30**), so "it must clear the rail" is applied as
  an edit but not yet locked in as a permanent test.
- **No decomposition** — "a gantry" still doesn't become a part list (**CALI-35**, M5).

---

## 🆕 CALI-28 — a Design: root prompt, part tree, per-part feedback history

**What's new:** the thing that was missing for conversational design — a durable container for *"the
thing I am building"*. Until now the only durable artifacts were a snapshot of one part (`runs/`) and a
hand-written assembly YAML; neither held the root prompt, the requirements you clarified once, or the
history of feedback on each part.

```bash
# 1. start a design (this is the root prompt — what we're trying to build)
caliper design new "a 3D printer gantry, 300x300x400 build volume"

# 2. see what designs exist
caliper design list

# 3. inspect one — requirements, the part tree, each part's feedback narrative,
#    and a measurement of the WHOLE design
caliper design show <slug>
```

A fresh design has no parts yet (the chat turn handler that authors them is **CALI-29**), so to see the
shape of it today, seed one from Python:

```bash
python - <<'EOF'
from caliper.design import DesignStore
from caliper.spec import Assertion

s = DesignStore.load("<slug>")                       # or DesignStore.create("a gantry")
s.add_requirement("extrusion profile?", "2040 V-slot")
s.add_requirement("belt or leadscrew on X?", "belt (GT2 6mm)", source="assumed")

box = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box({w},20,10)\n"
s.write_part("carriage", box.format(w=40), intent="the X carriage that rides the rail")
s.write_part("carriage", box.format(w=52), feedback="it needs to clear the rail by at least 1mm",
             action="refine")                        # a revision, with the feedback that caused it
s.assembly.assertions.append(Assertion(id="nothing_collides", expr="max_interference() <= 0"))
s.save()
EOF

caliper design show <slug>
```

**What you should see:**

```
▶ a 3D printer gantry, 300x300x400 build volume  [a-3d-printer-gantry-300x300x400-build]
  goal: a 3D printer gantry, 300x300x400 build volume
  units: mm

── 2 clarified requirement(s) ──
  • extrusion profile? → 2040 V-slot
  • belt or leadscrew on X? → belt (GT2 6mm)  [assumed]

── 2 part(s) ──
  • carriage         v2   [authored]  the X carriage that rides the rail
      ↳ "it needs to clear the rail by at least 1mm" → v2 (not measured)
  • rail             v1   [authored]  the MGN12 linear rail it rides on

── measuring the whole design ──
Measurement report — ALL PASS
  ✓ nothing_collides max_interference() <= 0  actual=0  (margin +0)
```

**Things worth poking at:**
- `ls designs/<slug>/parts/carriage/versions/` — **every revision is snapshotted**; nothing is
  overwritten. `DesignStore.restore("carriage", 1)` rolls back *as a new revision*, so the rollback is
  itself part of the history.
- `cat designs/<slug>/parts/carriage/history.jsonl` — the append-only record: what was asked, what
  changed, what it measured.
- `python -c "from caliper.design import DesignStore; print(DesignStore.load('<slug>').prompt_context('carriage'))"`
  — the **distilled context** a future revision of that part will see: goal, requirements, sibling
  parts, mates that must keep holding, enforced assertions, and a bounded tail of feedback. Not a
  transcript — that's what keeps it from growing without bound (conversational spec §2).
- Break a part on purpose (`raise RuntimeError('boom')` in its `part.py`) and re-run
  `caliper design show` — it **names the broken part and still measures the rest** (CALI-27's
  discipline, inherited).

**What this does NOT do yet** — deliberately, so the interaction gets proven before the hard parts:
- No chat. Parts are added from Python/CLI; the scope-aware turn handler is **CALI-29**, which also
  closes the real gap: *there is no code path today to refine a part that lives inside an assembly*.
- No decomposition. "A gantry" does not yet become a part list — that's **CALI-35 (M5)**.
- Feedback isn't promoted to assertions yet — that's **CALI-30**.

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

### 2026-06-13 · Hardening from real use (CALI-27)
**Fixed** (from Theo's reports): the **partial-machine bug** — one failed/slow part used to abort the
assembly load and strand a half-rendered machine; parts now load in parallel, the viewer renders what
worked, and the error bar **names the broken part with its actual exception**. Plus a **"❓ How this
works"** primer in the left panel (what to click, which actions need the API key), step-by-step Insert
hints, and a README **"▶ Run it"** block: `make serve` → **http://127.0.0.1:8000** (local only — it's
not hosted anywhere). Try it: load `corner-leg` in Assemblies — 4/4 parts, ALL PASS.

### 2026-06-13 · A whole small machine — a corner leg with measured bolt alignment (CALI-25/23/26)
**New:** Caliper now measures a **multi-part machine**, including whether the **bolt holes line up**.
The demo `examples/machine.yaml` is a corner leg: two solid **20×40 mm bars** (post + beam) at a right
angle, a **gusset bracket**, and a **foot**, screwed with M5s through aligned holes.
```bash
caliper assemble examples/machine.yaml
# → ALL PASS: 4 touch mates, nothing_collides, and three hole-alignment checks at ~0mm:
#     hole_misalignment(corner_bracket, bar_v) <= 0.5   ✓
#     hole_misalignment(corner_bracket, bar_h) <= 0.5   ✓
#     hole_misalignment(foot, bar_v) <= 0.5             ✓
```
Each part is a CadQuery script built at assemble time (CALI-23, B-rep kept → exact hole probes). The new
`hole_misalignment(a, b)` probe detects each part's holes, poses them into the assembly frame, and
returns the smallest axis offset between a near-parallel pair (0 = a screw passes straight through both).
In the **webapp** (Assemblies → corner-leg) the parts render with the bracket's bolt holes visible, and
any colliding pair is shaded **red** (CALI-26). To see the measurement bite: nudge a hole's coordinate
in one of `examples/machine/*.py` and re-assemble → the matching `*_bolts_align` check fails.
**See `TESTING.md` for the full hands-on walkthrough of everything built so far.**

### 2026-06-13 · Viewer UX — resize, panning, fit-to-view (CALI-21c)
**Fixed** (from real use on a second monitor): the 3D view now **resizes correctly across monitors/DPI**
(canvas always fills the panel, crisp at any pixel ratio); **middle-mouse (wheel-press) drag pans**
(CAD-style: left = orbit, middle/right = pan, scroll = zoom); and a **⤢ fit** button (or the `F` key)
**recenters** the view with the **ground grid sized to the content**. Just `make serve` and drag with the
wheel button, or hit `F` to refit after rotating away.

### 2026-06-13 · Webapp insert UI + assembly viewer (CALI-21b / 20b) ✅ live in-browser
**New:** the insert headline is now **clickable in the browser**. Open the Assemblies panel, load an
assembly, **click two parts in the 3D view to pick the interfaces**, choose a fit + what to insert, hit
Insert → the LLM authors the bridging part and it drops into the scene (green), with the whole assembly
re-measured. No CLI needed.
**Try it** (needs `ANTHROPIC_API_KEY`):
```bash
make serve        # → http://127.0.0.1:8000
# In the browser: open "Assemblies" → click "two-posts" → click the left post, then the right post
#   → set fit = slip, "what to insert" = a cross-bar → Insert ▶
# The green cross-bar appears between the posts; the report shows both mates at ~0.21mm (slip), no collision.
```
Assemblies are any YAML under `examples/` (override with `CALIPER_ASSEMBLIES`). An insert saves
`<id>.inserted.yaml` so it reappears in the list — load it and insert again to keep building.
**Verified live (2026-06-13, Preview MCP):** loaded two-posts, picked both, Insert → cross-bar authored
in 1 round, 0.21mm/side, ALL PASS — rendered green in 3D, no console errors.

### 2026-06-12 · Insert-into-assembly — the north-star headline (CALI-21) ✅ live
**New:** point at an assembly, name **two existing parts**, and Caliper makes the LLM **author a new
part that mates to both at a target fit** — built in assembly coordinates, *measured* against the real
posed parts, then added back to the assembly and re-verified. This is "insert a support between the
wheel and the XYZ assembly," working end to end.
**Try it** (needs `ANTHROPIC_API_KEY` — your `.env` has it):
```bash
make insert        # bridges examples/insert_demo.yaml (two posts, 50mm gap) with a cross-bar
#   caliper insert examples/insert_demo.yaml --between post_left,post_right \
#       --as crossbar --intent "a cross-bar" --fit slip --save examples/inserted.yaml
caliper assemble examples/inserted.yaml    # re-measure the assembly WITH the inserted part
```
**Verified live (2026-06-12):** the LLM authored the cross-bar on the **first round**, landing **0.21 mm
clearance to each post** — dead centre of the slip band (0.12–0.30). It reasons from the interface
bounding boxes, applies the clearance, and places the bar in world coordinates. Try `--fit press` / `free`
or a wider gap to watch it re-size. Want it taller? `caliper refine runs/run_NNNN "make it 6mm taller in z"`.

### 2026-06-12 · Multi-parameter optimizer — coupled fits (CALI-19b)
**New (loop-internal):** when a part has **two or more continuous dimensions** and a numeric check fails,
the decide step now tunes the **whole vector jointly** (`decide.tune_multi`) instead of one knob at a
time — so coupled fits (a clearance that depends on two dimensions, two mates sharing a wall) actually
converge. Coordinate descent does the cheap work; it **escalates to a global scipy search only when the
fits genuinely couple** (the case one-knob-at-a-time gets stuck on). No new command — `run`/`fit`/the
loop just solve harder fit problems now. Covered by `test_decide.py` (a coupled `W+D` / `W*D` problem).

### 2026-06-12 · Author-loop fit & refine — edit the real authored part (CALI-22)
**New:** `fit` and `refine` now work on **LLM-authored parts** (the ones with a `part.py`). They no
longer rebuild a bracket / refuse — they route through the author loop **seeded with the existing
script**, so the LLM revises the real part to clear a reference or apply a plain-language change.
**Try it — CLI** (needs `ANTHROPIC_API_KEY`):
```bash
caliper gen "a 50x30x6 mounting plate with an 8mm hole"        # → runs/run_00NN (writes part.py)
caliper fit runs/run_00NN --ref bolt=examples/obstacle.stl --fit slip   # LLM revises part.py to fit
caliper refine runs/run_00NN "add a 4mm chamfer on the top edge"        # LLM edits the real part
```
**Try it — browser:** `make serve` → "✦ author any part" → build → drop in a reference, pose it, **Fit**
(or type a change in the refine box). Both now edit the authored script instead of erroring. The header
reports the rounds + heals/revisions, same as `gen`.

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
