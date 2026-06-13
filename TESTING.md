# Caliper — testing guide

A hands-on walkthrough of everything built so far, how to exercise it, and what you should see.
Companion to [`pm/DEMO.md`](pm/DEMO.md) (chronological log) — this file is the "try it in order" guide.

> **The one idea:** measurement is the source of truth. Every feature ends in a *measured* report
> (`✓ / ✗` per assertion), not a render you have to eyeball.

---

## 0. Setup (once)

```bash
# Python env with OCCT/CadQuery (see pm/LOG.md for how it was built)
which python   # should be /opt/anaconda3/envs/caliper/bin/python  (or activate that env)

# Claude API key for the LLM paths (gen / insert / authored fit & refine).
# Put it in a gitignored .env at the repo root:
#   ANTHROPIC_API_KEY=sk-ant-...
#   CALIPER_MODEL=claude-...     (optional; defaults to claude-opus-4-8)
cat .env   # confirm ANTHROPIC_API_KEY is set

make test    # the regression guard — should report "<N> passed"
```

What needs the API key: `gen`, `insert`, and `fit`/`refine` **of an authored part**. Everything else
(the bracket `run`/`fit`/`refine`, `assemble`, the viewer) runs **offline**.

---

## 1. Single part — the bracket loop (offline, no key)

```bash
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"
# → drafts a spec, builds a real bracket, measures it, writes runs/run_00NN/part.stl
# Expect: a measurement report ending in ALL PASS, and an STL path.
```

Refine it (offline pattern refiner):
```bash
caliper refine runs/run_00NN "make the holes 8mm"
# Expect: "── changes (offline) ──  • holes 5.2 → 8.0", then a fresh run that re-measures.
```

Fit it to a reference at a fit class:
```bash
caliper fit runs/run_00NN --ref obstacle=examples/obstacle.stl --fit slip
# Expect: a clearance band "0.12 <= min_clearance(obstacle) <= 0.3"; the bracket resizes until the
# measured clearance lands in the band (~0.19 mm).
```

---

## 2. LLM-authored parts (needs the key)

```bash
caliper gen "a 50x30x6 mm mounting plate with a 8 mm hole through the center"
# Expect: "── authoring + iterating ──" then a verdict line ("✓ all checks pass after N round(s)")
# and runs/run_00NN/{part.stl, part.py}. part.py is the editable source of truth.
```

Refine / fit an **authored** part — these edit the real `part.py` (CALI-22):
```bash
caliper refine runs/run_00NN "add a 4 mm fillet to the top edges"
caliper fit    runs/run_00NN --ref bolt=examples/obstacle.stl --fit slip
# Expect: "── revising the script ──" / "── fitting the authored part ──" then a new run with an
# updated part.py. (Both make live LLM calls — 10–60 s.)
```

---

## 3. Assemblies — measure a multi-part design (offline)

```bash
make assemble                      # measures examples/assembly.yaml (a base→post→cap stack)
#   caliper assemble examples/assembly.yaml
# Expect: lists 3 parts + 2 mates, then ALL PASS (touch mates ≈ 0, nothing collides).
```

Make it **fail** on purpose: edit `examples/assembly.yaml`, set `post` `position: [0,0,10]` (so it
sinks into the base), re-run → the `post_on_base` mate **and** `nothing_collides` flip to `✗` with the
overlap volume as the actual. (That's the N-body collision measurement catching a real problem.)

---

## 4. Insert-into-assembly — the headline (needs the key)

```bash
make insert        # bridges examples/insert_demo.yaml (two posts, 50 mm gap) with a cross-bar
#   caliper insert examples/insert_demo.yaml --between post_left,post_right \
#       --as crossbar --intent "a cross-bar" --fit slip --save examples/inserted.yaml
# Expect: "✓ mates both interfaces after 1 round(s) · bridged 50mm", clearance ~0.21 mm to each post,
# then the whole assembly re-measured ALL PASS. Re-run `caliper assemble examples/inserted.yaml` to
# confirm the saved assembly (with the new part) still measures green.
```

---

## 5. The machine — a corner leg (CALI-25, offline)

The real test of the whole stack: parts that fit *and* whose bolt holes line up.

```bash
caliper assemble examples/machine.yaml
# Expect: 4 parts (bar_v, bar_h, corner_bracket, foot), 4 touch mates + 4 assertions, ALL PASS —
# including three hole-alignment checks at ~0 mm:
#   ✓ bracket_post_bolts_align   hole_misalignment(corner_bracket, bar_v) <= 0.5   actual≈0
#   ✓ bracket_beam_bolts_align   hole_misalignment(corner_bracket, bar_h) <= 0.5   actual≈0
#   ✓ foot_bolts_align           hole_misalignment(foot, bar_v) <= 0.5             actual≈0
```

The parts are CadQuery scripts in `examples/machine/` (built at assemble time, CALI-23). To see the
measurement *bite*, nudge a hole in one script (e.g. change a hole's `z` in `corner_bracket.py` by a
few mm) and re-assemble → the matching `*_bolts_align` check fails with the offset as the actual.

---

## 6. The webapp (browser)

```bash
make serve        # → http://127.0.0.1:8000
```
If you had a tab open from a previous version, **hard-refresh** (⌘⇧R) to pick up the latest assets.

- **Build / author / refine / fit** — the left panel: intent box (✦ author any part toggles the LLM
  author), refine box, and the "Fit to a reference" panel (drop an STL, drag/rotate it with the gizmo,
  Fit).
- **Recent parts** — click any past run to reload it.
- **Viewer controls** — **left-drag orbit, middle (wheel-press) drag pan, scroll zoom**; **⤢ fit**
  button or **F** to recenter. Resizes correctly across monitors/DPI.
- **Assemblies + Insert** — open the **Assemblies** panel, click an assembly (try **corner-leg** or
  **two-posts**). It renders all parts (gray = fixed, blue = movable, **green = an inserted part**,
  **red = a colliding part**). To insert: **click two parts** to pick interfaces → set fit + "what to
  insert" → **Insert ▶**. The authored bridge appears and the assembly re-measures.

---

## 7. Known rough edges / troubleshooting

- **Assemblies feel slow to load the first time.** Script-built parts (the machine) are compiled in a
  sandbox subprocess on first load (a few seconds each, 4 for the corner-leg). They're cached after, so
  it's snappy on reload. If a part fails to build, the report carries an `error` instead of 500-ing.
- **"authoring needs the Claude API"** on gen/insert/authored-refine → `ANTHROPIC_API_KEY` isn't set or
  is invalid. Check `.env`. These paths can't run offline.
- **Refine did nothing (offline path).** For a *bracket-family* part, the offline refiner only knows a
  few phrasings (holes, spacing, wall, ribs, cable bore); anything else needs the LLM path (toggle "use
  Claude"). For an *authored* part, refine always uses the LLM (and edits `part.py`).
- **Assembly part STL 404 / missing.** A part's `source` must resolve to an STL, a run dir (uses its
  `part.stl`), or a `.py` script — relative to the assembly file's directory (or `CALIPER_ASSEMBLIES`).
- **Assemblies list is empty in the webapp.** It scans `CALIPER_ASSEMBLIES` (default `examples/`) for
  YAMLs that parse as an assembly. Set `CALIPER_ASSEMBLIES=/path/to/dir` before `make serve` to point
  elsewhere.
- **Generated files** `examples/*.inserted.yaml` and `runs/` are gitignored (they point at local run
  dirs / are build artifacts).
- **Not on GitHub yet.** The repo has no `origin` remote; to push:
  `gh repo create caliper --private --source=. --remote=origin --push`.

---

## 8. Run the whole regression suite

```bash
make test     # pytest — the full guard
make review   # pytest + ruff + diff summary (ruff optional)
```
