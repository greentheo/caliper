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

- 🆕 **A build book a kid can follow (CALI-79, #47).** Pictures first, one step a page, one piece at a time, for an
  all-wood build; in the build package beside the shop's book.
- 🆕 **Test it (CALI-80, #48).** What the strength check predicts at each load (a sag range, and where it breaks),
  what to measure it with, and what the real one did; the card says how it went.
- 🆕 **A picture on it (CALI-78, #46).** "Put a T-rex on the side": drawn (or drawn by you on the pad), cut out of
  a panel nobody stands on, smooth enough for a jigsaw, and checked that it still holds; on the patterns and the
  cut sheet.
- 🆕 **Printed sides, carved (CALI-82, #54).** A part can be part plywood, part printed; its strength is checked
  in both materials, and the printed part can be carved down where it isn't working, every step checked.
- 🆕 **First run (CALI-59, #8).** One sentence, a few questions you can leave blank, **Build it**: Caliper builds
  it, checks it holds, draws the patterns and scores it, then answers the four questions. Or open the stool or
  the camper as a sample. Talk instead of typing; ask it to say it simpler; report what breaks if you want to.
- 🆕 **Will it hold? (CALI-54, #1).** A part that says what it must carry (`loads()`, written by the designer
  from "it has to hold me, 200 lb") gets a strength check: whittle's FEA with a stress picture, a plate check
  for a panel pushed face-on, the verdict, and where it should break.
- 🆕 **Four questions (CALI-72, #38).** What is it? Will it work? What do I buy? How do I make it? — a line each
  anyone can read, the engineer's numbers one click under it. Glue and screws are on the shopping list.
- 🆕 **Your shop (CALI-48, #4).** Tell it your tools and machines; every piece is planned with them, printed
  parts are split to fit your printer and costed, and anything your shop can't make is said.
- 🆕 **Patterns for hand tools (CALI-48, #4).** Every flat piece to measure and mark, print full size and tape,
  or project and trace — no CNC needed.
- 🆕 **The scorecard writes itself (CALI-55, #2).** What you say it must do becomes its checks: stated, assumed,
  or proposed for you to keep.
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

## 📓 Demo log

One file per entry, in [`demo/`](demo/). A PR adds a new file and never edits this section, so PRs don't conflict here.

- **Name:** `pm/demo/YYYY-MM-DD-HHMM-cali-N-short-title.md`. The time only sorts entries within a day.
- **Contents:** `### YYYY-MM-DD · what you can try (CALI-N #issue)`, then the exact steps.
- **Read it, newest first:** `make demo-log`.
