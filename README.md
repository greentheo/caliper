# Caliper

> Spec-driven, **measurement-grounded** generation of manufacturable 3D parts.
> Natural language in → executable spec → generated mesh → measured against the spec → iterate until it passes.

Caliper is "test-driven development for physical parts." Instead of emitting CAD blind and eyeballing a render, every generated part is **measured exactly** (bounding box, wall thickness, hole inventory, mass, interference, watertightness) and graded against assertions in a spec. Numbers are ground truth; the render is only a sanity check.

See [`specs/caliper-design-spec.md`](specs/caliper-design-spec.md) for the full design.

## Status

Phase 0 (MVP). Building the core loop library first, UI second. See the project board: [`pm/BOARD.md`](pm/BOARD.md).

## Quickstart

```bash
# 1. Create the environment (CadQuery/OCCT via conda-forge)
conda env create -f environment.yml
conda activate caliper

# 2. Install the package (editable)
pip install -e ".[dev]"

# 3. Run the regression guard
pytest
```

> Note: in this machine's sandbox the `conda` shell function is blocked; call the binary
> directly, e.g. `/opt/anaconda3/bin/conda env create -f environment.yml`.

## Layout

```
src/caliper/        # the library — the loop is the product
  spec.py           # CALI-1  typed spec schema (params, refs, assertions, machine)
  measure.py        # CALI-2  measurement API (bbox, mass, walls, holes, watertight…)
  evaluate.py       # CALI-3  evaluator: assertion exprs → {pass, actual, margin}
tests/              # regression guard (pytest) against known parts
pm/                 # lightweight .md project management (board + tasks + log)
nightshift/         # local looping/review/test scaffolding (adopted from ai-night-shift)
specs/              # design spec
```

## Working conventions

We run this like an engineering shop: specs → backlog → in-progress → done, with a work log.
- **Board:** [`pm/BOARD.md`](pm/BOARD.md) — kanban of every task.
- **Tasks:** [`pm/TASKS.md`](pm/TASKS.md) — the "issues" with acceptance criteria.
- **Log:** [`pm/LOG.md`](pm/LOG.md) — append-only record of what shipped, when, with commit hashes.
- **Loop/review:** [`nightshift/`](nightshift/) — `make loop` to run an iteration, `make review` for the regression+review guard.
