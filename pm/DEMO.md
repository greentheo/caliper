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

- 🆕 **Will it hold? (CALI-54, #1).** A part that says what it must carry (`loads()`, written by the designer
  from "it has to hold me, 200 lb") gets a strength check: whittle's FEA with a stress picture, a plate check
  for a panel pushed face-on, the verdict, and where it should break.
- 🆕 **Make it lighter (CALI-71, #32).** Holes where the wood isn't working, cut all the way through, rim and
  webs a jigsaw can handle, each step re-checked; adopt one and every later build cuts it.
- 🆕 **Studies (CALI-70, #31).** One page with every study of the design, and what each part can run next.
- 🆕 **How it's built, in 3D (CALI-52).** Any part that says what it's built from can show its pieces in the
  viewport — panels, skeleton, tubes, plates — in layers you switch on and off.
- 🆕 **Scorecard (CALI-47).** One card per design: checks and objectives across design, strength/mass/drag,
  making, and cost & waste — each number with how far to trust it, and what changed since last time.
- 🆕 **Cut plan (CALI-45).** Any part that says what it's built from gets a cut plan: its panels unfolded
  and nested onto real sheets by Theo's unfold-to-sheets (SVG + DXF per sheet, score lines where a panel
  bends, seam tokens, a printable PDF), and its sticks cut-listed.
- 🆕 **Walls that carry load (CALI-44).** A part can say how its walls work as structure (`shell()` —
  foam sandwiches as deep beams); the frame study solves them with the tubes and says how strong each wall
  is and what its fixings carry. Fiberglass skins are a construction choice (cloth + epoxy in the shopping list).
- 🆕 **Room for the mattress (CALI-42).** A part can say what it has to hold (`keeps()` — the twin
  mattress, a pale slab under **Built from**) and how far a drag study may take each number (`RANGES`, ticked
  for you). The search keeps the outside out of the slab, and every design it returns is re-checked.
- 🆕 **The frame carries the box as built (CALI-43).** **Size the frame** → *carries: the design as built*
  puts every panel, post and payload pound where it sits onto the nearest tube; pick a **layout** (the X
  frame has four) and compare runs; the panel names what holds the safety back and the hardest-worked joint
  (what a gusset there carries).
- 🆕 **What it's built from (CALI-41).** Select a part that says what it's built from (the camper box) →
  **Built from**: its weight, where its centre of gravity sits (red dot), what it's made of, and **what to
  buy**. Change the floor to ¼ in, drop the posts, add paint inside — the weight and the hitch moment update;
  nothing saves until **Use these**. With nothing selected, **Weight & balance** shows the whole design and
  what the hitch carries (add a payload).

- 🆕 **Shape it for drag — numbers back (CALI-39).** Select a part → **Shape it for drag**: whittle searches
  the numbers in its script (tail length, top drop, side pinch, edge radius…) against its drag model, with
  the car as a real obstacle. Pick a design from the slider → **Use these numbers** → they're written into
  the script. The part stays parametric — no mesh, no remesh inflation.

- 🆕 **The design session, in the browser (CALI-31/32/33).** `make serve` → **http://127.0.0.1:8000** now
  opens a **viewport + a conversation**: describe what you're building, answer a few questions, then
  **click any part and talk about it**. The inspector shows its size (inches or mm), the rules locked in
  on it, and its history. Long turns stream their progress. The old control panel lives at `/classic`.
- 🆕 **whittle bridge (CALI-38).** With whittle running (`python -m whittle.gui` in `~/githubrepo/whittle`),
  select a part → **Send to whittle** → a slider of shapes with the drag they save, in **kWh per 100 mi** →
  click one to see it in place → **Bring this back**. "Roll it back" returns to the parametric part.

- 🆕 **Feedback becomes a test (CALI-30, M4).** Say *"it must clear the rail by at least 2mm"* and
  Caliper doesn't just make the change — it drafts the **assertion** that locks it in
  (`min_clearance(carriage, rail) >= 2.0`), **validates that it actually measures**, and offers it. Say
  **yes** and every future revision is checked against it, forever, by the same evaluator that grades
  everything else. Say **no** and it stays a one-off. Unmeasurable feedback is labelled as such, never
  faked into a number — and if a new rule contradicts one you already locked in, it says so.

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

## 🆕 CALI-39 — shape it for drag, and keep it parametric

**What's new:** instead of whittle carving a mesh, whittle searches the **numbers** in the part's script,
and the one you pick is written back into it. Built with the whittle-agent session.

**Needs** whittle at `a1248d1` or later (its `physics-and-slider` branch — `ParametricStudy` and
obstacles) installed into Caliper's environment (already done on Theo's machine):

```bash
/opt/anaconda3/envs/caliper/bin/python -m pip install -e ~/githubrepo/whittle
```

**Try it (hitch box):**
1. Select the box. Under **Shape it for drag**, its `PARAMS` are listed. If it says the script has none,
   click **Make it tunable** — the chat restructures it and adds `tail_len`, `tail_drop`, `tail_pinch`,
   `tail_edge_r`, all 0 (the shape doesn't change).
2. Leave the tail numbers ticked (suggested ranges are filled in; widen `tail_len` to ~700), make sure the
   Leaf block is ticked under **rides behind**, 65 mph, 15%, *normal* → **Shape it**. ~3 minutes; it shows
   build count and time left.
3. Click a row to see that design in place. **Use these numbers for box** writes them into its script.

**What it found, live:** a ~16° boat tail — the last 500 mm tapers, the top falls 146 mm, each side draws
in 140 mm — about **11 lbf less than the square box ≈ 2.2 kWh per 100 mi** at 65 mph (estimated; treat as
±30%), giving up 7% of the box's volume. The box's outside is still exactly 39 × 74 × 41 in at the front,
floor at 18 in.

**Things worth knowing:** act on the **savings**, not the totals — behind the car the model scores the
box alone, so it misses the box partly filling the car's wake; what the box really costs the car is
likely lower, and the savings, if anything, conservative. `tail_len` hit its 500 mm limit (the page now
names a pinned parameter), so a longer taper may help — then the volume you allow becomes the limit.
Flat-panel tapers should settle around 12–18°: the model's flow starts tearing off near 20°. Building
candidates uses a warm worker, ~0.1–0.3 s each. Every new part is now written with its dimensions in `PARAMS`, so
it can be shaped this way without the restructure step.

---

## 🆕 CALI-31/32/33/38 — design in the browser, study it in whittle

**What's new:** the design session is the home page, and a part can go to **whittle** for an aero or
load study and come back. Built for Theo's hitch cargo box behind the Leaf.

**Start both tools:**

```bash
make serve
```

```bash
cd ~/githubrepo/whittle && .venv/bin/python -m whittle.gui --no-browser
```

Open **http://127.0.0.1:8000**. The dot top-right goes green when whittle is reachable.

**Walkthrough — the hitch box:**
1. **+ New design** → describe it, e.g. *"a cargo box on the trailer hitch behind my Nissan Leaf: 74 in
   wide, 41 in high, 39 in deep, 18 in behind the car, on a 2 in square steel tube frame that slides into
   the receiver; foam covered in poor man's fiberglass, with a door and a roof fan."* Because you wrote
   inches, it shows inches (the model is always mm).
2. **Answer the questions** (receiver height, hatch clearance, …) or **Just build it** — blanks become
   *assumed* requirements, labelled as such, and every part is built against them.
3. **Build parts by talking:** *"build a block standing in for the rear of the Leaf: 70.5 in wide, from
   6 in to 61.4 in off the ground, its rear face at x = 0, extending forward 60 in"* → then *"now the box"* →
   then *"the frame"*. Coordinates: the car drives **+X**, **Z up**, ground at z = 0, y = 0 on the centreline.
4. Click the Leaf block → tick **treat as a reference** (it turns translucent grey).
5. Click the box → in the inspector **whittle** panel: study *airflow*, carve **the tail only** (the default
   once something is a reference), 65 mph, 20% → **Send to whittle**. ~2–3 minutes, progress streams.
6. Read the table — the **saved lbf** and **kWh/100mi** columns are the ones to act on. Click a row to see
   that shape in place (the original box as a blue ghost). **Bring this back as box** to adopt it; if it
   grew anywhere, the chat says so. **"roll it back"** in chat returns to the parametric box.

**What it found, live, for that box (tail only, 65 mph):** about **8 lbf saved ≈ 1.7 kWh per 100 mi**
from tapering the rear ~8% of the box, after which more carving stops helping. Free air claims far more
(~107 lbf) but gets it by rounding the *front* — which, behind the car, sits in its wake.

**Things worth knowing:**
- whittle's drag model **ranks** shapes well; absolute numbers are good to perhaps 30%, and it can't
  model the car's wake yet. That's why the tail-only study exists.
- whittle rebuilds parts on a voxel grid, so its shapes come back slightly bigger (~1 in at this size).
  "removed" is measured against **your** part, so station 0 may read negative; bringing one back reports
  the growth.
- A whittled part is a **mesh** — chat won't revise it (that would throw the carving away); roll back first.
- `designs/<slug>/whittle/<run>/` holds every station STL and the run record.

**What this does NOT do yet:**
- **Shelter behind the car** — needs whittle to accept obstacle bodies (raised with the whittle-agent).
- **A parametric shape back** (CALI-39) — today a station returns as a mesh; the parametric loop
  (Caliper's parameters, whittle's drag score, Caliper's optimizer) is next.
- The **frame's** strength is not a whittle job — 2 in steel tube walls are far finer than its voxels.
  That's beam math (moment at the receiver), and Caliper can assert it.

---

## 🆕 CALI-30 — say it once, and it's a test forever

**What's new:** the thing that makes the whole conversational approach hold up. A chat tool that only
*edits* drifts — you ask for something, it happens, and nothing stops revision #14 from undoing it.
Caliper turns measurable feedback into an **assertion**, enforced by the same evaluator that grades
everything else.

Continuing from the CALI-29 gantry:

```bash
caliper chat gantry "the carriage must clear the rail by at least 3mm" --part carriage
```

```
✓ revised **carriage** → v5 (1 round(s))
Every check on this part passes.
The whole design still measures green.

💡 I can lock that in as a test on the design:
    carriage_rail_clearance: min_clearance(carriage, rail) >= 3
    ✓ it holds now (measured 6). Every future revision would be checked against it.
    Say **yes** to enforce it, or **no** to leave it as a one-off change.
```

```bash
caliper chat gantry "yes, lock it in"
```

```
✓ Locked in on the design: **carriage_rail_clearance** — `min_clearance(carriage, rail) >= 3`
Every future revision is measured against it; if something breaks it, I'll say so.
```

From here it's a **test**. Any later revision — of any part — that violates it gets named:

```bash
caliper chat gantry "move it closer to the rail" --part carriage
```

```
⚠ This change **broke 1 design check(s)** that passed before:
  • carriage_rail_clearance: min_clearance(carriage, rail) >= 3 → actual=1.0 (margin -2)
```

**Things worth poking at:**
- `cat designs/gantry/assembly.yaml` — a cross-part rule lands in `assert:` on the assembly, so it's
  checked when **anything** changes. A rule about one part alone
  (`caliper chat gantry "it must be no taller than 40mm" --part carriage`) lands in
  `designs/gantry/parts/carriage/spec.yaml` instead, where the author loop enforces it every revision.
- Say something vague: `caliper chat gantry "make it look less chunky" --part carriage` — no proposal,
  no invented number. But phrase a rule it *can't* measure — **"it must look less chunky"** — and it
  tells you plainly that it can't be enforced, instead of letting you assume it stuck.
- Ask for something that contradicts a rule you locked in
  (`"it should sit within 1mm of the rail"` after locking in `>= 3mm`) and it names the clash:
  *"It contradicts a rule you already locked in — carriage_rail_clearance. Both can't hold. Saying yes
  replaces that older rule with this one."*
- `cat designs/gantry/parts/carriage/history.jsonl` — every promotion records the **feedback it came
  from**, so months later you can ask why a rule exists and get the sentence that created it.
- `cat designs/gantry/pending.json` after an offer — the proposal is parked between turns. A new change
  supersedes it; a rollback drops it. It's never silently accepted.

**Why the two-step matters:** an over-constrained spec fails in confusing ways, and you have to know
which rules exist. Nothing is ever promoted without you saying yes.

**What this does NOT do yet:**
- **No UI** (**CALI-32**) and **no streaming** (**CALI-31**) — same as CALI-29.
- **No way to drop a rule by name** in chat. Accepting a *contradicting* rule retires the one it
  replaces, but otherwise you edit `assembly.yaml` / the part's `spec.yaml` by hand.
- **No decomposition** — "a gantry" still doesn't become a part list (**CALI-35**, M5).

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

### 2026-10-30 · Make the stool lighter, in holes a jigsaw can cut (CALI-71 #32)
1. Open the stool, click it, **Will it hold? → Make it lighter → Lighten the panels** (about a minute). The
   table goes from solid to four rounded windows (49% of the walls, 3.3 lb lighter), each step checked again.
2. Click a step to see it in place (orange). **Cut these holes in step_stool** makes it the part: its weight
   drops under **Built from**, and every later revision keeps the holes.
3. **Other thicknesses → Use** on 5/8 in asks the designer to make it from 5/8 in plywood.
4. Make the build package: the book has a **Will it hold?** page with the predicted breaking load and a blank
   for the measured one.
5. Offline: `python -m pytest tests/test_lighten.py`.

### 2026-10-30 · A stool gets a stool's panels; a part says what it is now (CALI-67 #27, CALI-69 #29)
1. `make serve`, open the stool, click it: **Size, Rules, Will it hold?, Built from, History** — no drag
   study, no carving. With nothing selected, **Weight & balance** is the weight and the red dot, no hitch.
   **Studies** says why there's no drag study, and that saying it moves through air brings them back.
2. Open the cargo box: the hitch moment and both drag studies are still there.
3. On the stool, **Will it hold? → Show the stress**: blue to red, no red dot in the way, and the bar
   says the colours are the FEA's while the verdict is the plate check's.
4. Ask the stool for any change (say, "make it 10 in tall"): its description under the part name is
   rewritten from the new script — one platform, five panels — instead of "two-step".

### 2026-10-29 · Will it hold Dad? And every study on one page (CALI-54 #1, CALI-70 #31)
1. `make serve`, open **A step stool so my 6-year-old…**, click the stool, and say *"It has to hold me too:
   200 lb, stepping up onto the top."* It comes back as a revision (v3) with what it must hold, and the reply
   says it's checked under **Will it hold?**.
2. In the stool's panel, **Will it hold? → Check it holds** (about 15 s; whittle needs only to be installed,
   not running). It holds at **3.1x**: the plate check on the top, with the grain the wrong way (6.2x the right
   way), and where the FEA says it works hardest. The viewport shows the stress, red under the foot, with
   the load's box and an arrow. **Other thicknesses** says 5/8 in would still hold and 1/2 in wouldn't.
3. **Studies** (header): what each part can run and why the rest can't yet, and every run so far. **Open** on
   the strength row goes straight back to the stress picture.
4. Offline: `python -m pytest tests/test_load_study.py tests/test_studies.py`.

### 2026-10-29 · The designer writes what it's built from: a stool from one sentence to a cut sheet (CALI-54, #1)
1. `make serve`, then **+ New design**: *"A step stool so my 6-year-old can reach the bathroom sink. Made
   from 3/4 in plywood, glued and screwed. It has to hold me too (200 lb)."* → **Use these answers**.
2. Say **build the stool**. The part comes back with a weight under **Built from** (no script written by
   hand): its panels by name, one 4x8 sheet of plywood, paint.
3. Click the stool → **Make the cut plan**: one sheet, the panels nested and labelled (DXF, SVG, PDF).
4. To see the check bite, move one panel in the part's `construction()` (add 300 to a y) and ask for any
   change: it takes an extra round, because the first fails `construction_inside`, naming the panel and how
   far out it is, and the designer puts it back. `python -m pytest tests/test_consistency.py` runs the same
   cases offline.

### 2026-10-29 · Open source: issues, licence, CI, install for a stranger (CALI-60, #5)
**Try it:**
- Open work: https://github.com/greentheo/caliper/issues (V1 is milestone 1). Each title starts with its
  CALI id. `pm/BOARD.md` is history now, with a map from old cards to issues.
- CI: every PR runs the suite on GitHub (PR #25's first run: 447 passed, none skipped).
- `make tools` installs the optional tools at pinned commits (whittle into the env, unfold-to-sheets into
  `vendor/`). On your machine it says both are your own checkouts and leaves them alone (`vendor/` is a link
  to `~/githubrepo/game-dev/unfold-to-sheets`).
- The README's Install section is the stranger's path: clone, micromamba, `make install`, `make tools`,
  `.env`, `make test`. CONTRIBUTING.md covers issues, commits, what "done" means, and the optional tools.

### 2026-10-28 · The build package (CALI-51)
**Try it:** open the camper with nothing selected → **Build package** (under the scorecard) → *Open the build
book*. One printable page: the cover (ready to cut, 11/11, the headline numbers), what to watch before you
cut, the shopping list with checkboxes, the cut lists (tubes with their end cuts, the 1x2s and 2x2s, the
gusset plates, every nested sheet), the eleven assembly steps — each drawn, the new pieces in colour on the
pale ones already there — and the scorecard as released. *PDF* is the same book; *Download all (.zip)* has
the plasma DXFs, the router DXFs + 1:1 pattern PDFs, the cut list, shopping list and the scripts as
released. *Make a new build package* after any change releases 002 (it re-runs a stale cut plan and
re-scores first).

### 2026-10-28 · Parked on the jacks (CALI-53)
**Try it:** *Score it* on the design — the scorecard now has the parked case: the frame on the hitch and two
jacks under the X's back corners with someone kneeling anywhere (2.24×), the floor under a knee on the
mattress (3.3×), the most a jack carries (288 lb), and the hitch at 356 lb with someone kneeling at the very front —
under Theo's 420 lb (the 350 lb rating + 20%). All 11 checks pass. The settings (person, gear, knee) are in `scorecard.yaml` under `parked`.

### 2026-10-28 · See how it's built (CALI-52)
**Try it:** click **cargo_box** → **Built from** → *Show how it's built*. The box turns into its pieces: pink
foam panels, the shell bands, the tan floor, teal glass patches on the front corners, and the 1x2 frames with
three 2x2 roof beams. The panel at the top left of the viewport switches each layer off — untick *end & side
panels* and *shell* to see the skeleton on its own. Do the same on **frame**: the tubes and the brass gusset
plates at the riser's corners. *the solid, faint* brings back the outline; × puts a part back to its solid.

### 2026-10-28 · The skeleton, searched under snow (CALI-52)
**Try it:** click **cargo_box** → **Built from**: the new choices — *frame posts* (the box inside the box),
*roof beams* (how many), *roof beam*, *roof beam dir* (front to back or across), *skin in*. It's set to the
search's answer: 1x2 frames and two 2x2 beams across. Try *roof beams 0* and score the design: the
scorecard's snow check fails (the foam cracks underneath); put them back. The cut plan lists the 1x2 frame
pieces and the beams. With nothing selected, the **Scorecard** shows Theo's constraints in his words:
tongue weight, surviving 3.5×, snow at 2×.

### 2026-10-28 · The scorecard (CALI-47)
**Try it:** open the camper with nothing selected — **Scorecard** is at the top: every check (✓/✗, the
number, how far to trust it) and every objective, with the stock bill (*Stock: $446 · offcut $…* opens the
lines). *Score it* re-scores the design as it stands (~10 s): try a what-if in a part's **Built from** and
*Use these*, then score again — the objectives show what changed. The one ✗ is the hitch against an
*assumed* Class II rating; the goals live in `designs/a-cargo-box-on-the-trailer/scorecard.yaml`.

### 2026-10-28 · Gusset plates (CALI-46)
**Try it:** click **frame** → **Size the frame** → scroll to *Gusset plates*: the riser's two corners, each a
slider from a solid plate to the lightest that holds (1/8 in shown; pick 3/16 or 1/4 and *Size the gussets*
to compare). The highlighted row is the one in use — each takes 82–84% of the bending off its corner weld.
**Built from → Cut plan** draws them for the plasma table (DXF in mm) alongside the tube cut list (shank
11.75 in, riser 10 in, spine 36.75 in, X 4 @ 40.92 in mitred 27°).

### 2026-10-28 · The cut plan (CALI-45)
**Try it:** click **cargo_box** → scroll to **Built from → Cut plan**. 1 sheet of ⅜ ply and **4 sheets of 1 in
XPS** — click a sheet to open it full size: the front panel with the shoulder bands nested round it, dash-dot
(mountain) and dashed (valley) score lines at the nose and tail ends of the bands, a seam token on both sides
of every joint. *sheet N DXF* goes to CAM; *printable PDF* has a scale bar; *which piece is which* draws them
on the box. The 2x2 post cuts are listed underneath. Click **frame** → its cut plan has the tube cut list
(13 in shank, 8 in riser, 38 in spine, four 42 in X arms) and the two gusset halves. *Make it again* after a
change; the panel says when the plan is out of date. Needs node and `game-dev/unfold-to-sheets` (or
`CALIPER_UNFOLD_DIR`).

### 2026-10-28 · The box moves in and carries itself (CALI-44)
**Try it:** the camper is now drag design 2, 3 in behind the bumper (the hatch rule is gone; *bumper_clearance*
passes at 3.0 in). Click **cargo_box** → **Built from** → set *skin out* to *fiberglass*: 52.3 → 47.5 lb, and
*To buy* turns into glass cloth + epoxy. Click away → **Weight & balance** with 50 lb: **3,428 lb·in** on the
receiver (it was ~8,000 at 18 in with 100 lb). Click **frame** → **Size the frame**: the three newest runs carry
the box as built with 50 lb — *walls count* (PMF), *walls count · fiberglass*, and tubes only; each says how
strong the walls are and what a fixing carries. The frame you see is design 6 of the PMF run: 50.5 lb, 4.5×.
Untick *the box's walls carry load too* to compare.

### 2026-10-28 · Room for a mattress, curvier sides, and an X frame (CALI-42/43)
**Try it:** open *A cargo box on the trailer…* → click **cargo_box**. It's 77 × 40 × 41 in now (75 × 38 inside
the 1 in walls); **Built from** says *✓ holds the mattress* and the pale slab at its base is that space.
Scroll to **Shape it for drag**: the eight ticked numbers and their ranges are the part's own. The last search
(behind leaf_rear, 65 mph, 2,738 builds, 40 min): **design 2 gives up 9% of the volume and saves 22 lbf ≈
4.4 kWh/100 mi**, design 3 24 lbf ≈ 4.7 — click a row to see it in place (round front above the mattress, sides
leaning in, a tapered tail, the slab untouched). *Use these numbers* saves one. Then click **frame** in the
parts list → **Size the frame**: six runs in the picker, one per layout (and two with the X held to 1 in tube),
all carrying the box as built + 100 lb on the floor. None reaches 3.5× — the panel says why (the shank in the
receiver). Try *payload 50* on *X only* → about 3.2×.

### 2026-10-27 · What it's built from — weight, balance, a shopping list (CALI-41)
**Try it:** open *A cargo box on the trailer…* → click **cargo_box** → scroll to **Built from**. 56.1 lb with a
⅜ in floor; the red dot is its centre of gravity. Set *floor t* to ¼ in → 48.9 lb and the hitch moment drops
from 4,774 to 4,481 lb·in; **Back to saved** undoes it. **To buy**: 1 sheet of ⅜ ply, 4 sheets of 1 in XPS,
two 8 ft 2x2s (4 @ 39.6″), 5.9 yd of 60″ canvas. Click away from the parts → **Weight & balance**: the 2 in
frame is 72 lb of the 128 — put 150 lb of payload on the floor to see a loaded trip.

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
