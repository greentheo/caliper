# Caliper

> Spec-driven, **measurement-grounded** generation of manufacturable 3D parts.
> Natural language in → executable spec → generated mesh → measured against the spec → iterate until it passes.

Caliper is "test-driven development for physical parts." Instead of emitting CAD blind and eyeballing a render, every generated part is **measured exactly** (bounding box, wall thickness, hole inventory, mass, interference, watertightness) and graded against assertions in a spec. Numbers are ground truth; the render is only a sanity check.

See [`specs/caliper-design-spec.md`](specs/caliper-design-spec.md) for the full design.

## ▶ Run it (the two commands that matter)

```bash
make serve     # the webapp →  http://127.0.0.1:8000   (local only; Ctrl-C to stop)
make test      # the regression guard (pytest)
```

The webapp is **not hosted anywhere** — it runs on your machine when `make serve` is running, at
**http://127.0.0.1:8000**. Hard-refresh (⌘⇧R) after an update. LLM features (✦ author any part,
Insert, refining authored parts) need `ANTHROPIC_API_KEY` in a gitignored `.env` at the repo root.
**New here? [`TESTING.md`](TESTING.md) is the full hands-on walkthrough.**

## Status

The single-part loop **and** the assembly spine are complete: intent → spec → LLM-authored CadQuery →
measured → revised → fitted → **inserted into multi-part assemblies with measured fits and bolt-hole
alignment** (see the corner-leg machine: `caliper assemble examples/machine.yaml`). See the board:
[`pm/BOARD.md`](pm/BOARD.md).

## Quickstart

```bash
# 1. Create the environment (CadQuery/OCCT via conda-forge).
#    micromamba is STRONGLY recommended here — Anaconda's classic solver took 55+ min and stalled
#    on cadquery; micromamba solves the same env in seconds.
micromamba create -p /opt/anaconda3/envs/caliper -c conda-forge -y python=3.11 cadquery
/opt/anaconda3/envs/caliper/bin/python -m pip install -r requirements-pip.txt
#    (declarative equivalent, if your solver can handle it: `conda env create -f environment.yml`)

# 2. Install the package into the env (makes the `caliper` command available)
make install

# 3. Run the regression guard, and try the loop — both auto-resolve the env (no activation needed).
make test
make run INTENT="a 60 mm corner bracket for 2020 extrusion with four M5 holes"

# 4. Or jam in 3D space — the webapp (3D viewer, refine loop, STL download, SpaceMouse):
make serve            # → http://127.0.0.1:8000
```

> No need to activate anything for `make` targets — they resolve `/opt/anaconda3/envs/caliper`
> directly (override with `CALIPER_PY=/path/to/python`). To activate for ad-hoc use, `conda` works
> on a path: `conda activate /opt/anaconda3/envs/caliper` (micromamba was only a throwaway build tool).

> Note: in this machine's sandbox the `conda`/`micromamba` shell functions may be blocked; call the
> binary directly (e.g. `/tmp/bin/micromamba …`). The canonical env lives at
> `/opt/anaconda3/envs/caliper`, which `make test` resolves automatically.

## Layout

```
src/caliper/        # the library — the loop is the product
  spec.py           # CALI-1  typed spec schema (params, refs, assertions, machine)
  measure.py        # CALI-2  measurement API (bbox, walls, holes, interference, hole alignment…)
  evaluate.py       # CALI-3  evaluator: assertion exprs → {pass, actual, margin}
  decide.py         # CALI-7/19b  optimizer routing (1-D snug + multi-param joint tuning)
  authoring.py      # CALI-16/17/22  LLM writes/revises the CadQuery (gen, refit, refine)
  assembly.py       # CALI-20/23  N parts + named mates + assembly assertions; .py part sources
  insert.py         # CALI-21  author a part that mates two named interfaces
  server.py + web/  # CALI-9/21b  the webapp (three.js viewer, assemblies, insert UI)
tests/              # regression guard (pytest) against known parts
examples/           # demo specs, assemblies, and the corner-leg machine (machine.yaml)
pm/                 # lightweight .md project management (board + tasks + log)
specs/              # design spec
TESTING.md          # ← the hands-on walkthrough of everything
```

## Working conventions

We run this like an engineering shop: specs → backlog → in-progress → done, with a work log.
- **Board:** [`pm/BOARD.md`](pm/BOARD.md) — kanban of every task.
- **Tasks:** [`pm/TASKS.md`](pm/TASKS.md) — the "issues" with acceptance criteria.
- **Log:** [`pm/LOG.md`](pm/LOG.md) — append-only record of what shipped, when, with commit hashes.
- **Demo & testing:** [`pm/DEMO.md`](pm/DEMO.md) — **start here to try the build**: current
  capabilities + the exact commands to run each shipped feature. Updated after every task.
- **Loop/review:** [`nightshift/`](nightshift/) — `make loop` to run an iteration, `make review` for the regression+review guard.
