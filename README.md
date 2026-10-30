# Caliper

> Say what you want to make. Caliper designs it, tests it, plans the build and prices it, and re-runs all
> of it when you change anything.

Caliper is test-driven development for physical things. Claude writes the geometry as a CadQuery script;
Caliper measures every part exactly (size, walls, holes, mass, interference, watertightness) and grades it
against what you asked for, revising until it passes. The numbers are the ground truth; the render is a
sanity check.

## What it does

- **Design.** The home page is a 3D viewport and a conversation. Ask for something and Caliper asks a few
  questions, writes the part, measures it and revises it. Click a part to talk about just that part.
  Feedback you give can become a rule the design keeps from then on.
- **Test.** Studies through [whittle](https://github.com/greentheo/whittle): drag (a shape searched for
  less drag, even sheltered behind a car), tube frames sized for their load cases, and gusset plates
  lightened where the load doesn't go.
- **Plan the build.** What it's built from (weight, centre of gravity, bill of materials), and cut plans
  through [unfold-to-sheets](https://github.com/greentheo/unfold-to-sheets): panels flattened and nested
  onto real sheets, folds scored, written as DXF, SVG and PDF, plus tube end cuts.
- **Price it.** A scorecard of checks and objectives, with cost and waste at prices you can edit.
- **Release it.** A build package per revision: a build book (HTML and PDF) with the assembly drawn step
  by step, plasma and router files, cut lists and a shopping list.

## Status

Early, and moving fast. It works end to end on its author's own projects (a cargo box towed behind an
electric car, from aero shaping to the build book). A design started from scratch in the chat now gets
what it's built from, its bill of materials and its cut plan (a plywood step stool goes from one sentence
to a nested sheet), and when it says what the part must carry, a strength check (does the stool hold an
adult stepping onto it, and by how much). Every study a design has is on one page. The road to an
installable app is the [V1 milestone](https://github.com/greentheo/caliper/milestone/1).

## Install

You need macOS or Linux, git, and [micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html)
(or conda). Cut plans also need [node](https://nodejs.org) 20 or later. The designer needs an
[Anthropic API key](https://console.anthropic.com/settings/keys); the offline paths need none.

```bash
git clone https://github.com/greentheo/caliper.git
cd caliper
micromamba create -n caliper -c conda-forge -y python=3.11 cadquery
micromamba activate caliper
pip install -r requirements-pip.txt
make install            # Caliper itself, editable, with the `caliper` command
make tools              # optional: whittle (studies) and unfold-to-sheets (cut plans), pinned
cp .env.example .env    # then set ANTHROPIC_API_KEY
make test               # the suite, about 10 minutes
```

CadQuery's geometry kernel (OpenCascade) is a native build that conda-forge ships, which is why the
environment starts there. micromamba solves it in seconds; Anaconda's classic solver can take an hour.
`make` uses the activated environment's Python (or set `CALIPER_PY=/path/to/python`).

## Run it

```bash
make serve              # → http://127.0.0.1:8000
```

It runs on your machine only; nothing is hosted. Start a design from the home page; the older control
panel is at `/classic`. The command line drives the same engine:

```bash
caliper gen "a phone stand for a 7 mm thick phone"        # Claude writes a part, measured until it passes
caliper run "a 60 mm corner bracket with four M5 holes" --no-llm   # the offline bracket generator
caliper assemble examples/machine.yaml                     # measure a multi-part assembly
caliper --help                                             # spec, refine, fit, insert, design, chat, serve
```

[`TESTING.md`](TESTING.md) walks through the command line and the classic panel step by step.

> **Caliper runs the Python that Claude writes**, on your machine, in a separate process with a timeout.
> That stops runaway or buggy scripts; it is not a security sandbox. Only open designs from people you trust.

## How it fits together

```
src/caliper/
  spec.py, measure.py, evaluate.py      what a part must be, measured, graded
  authoring.py, sandbox.py              Claude writes and revises the CadQuery; it runs in a worker process
  part_scripts.md, consistency.py       what a part script declares, and the check that it matches the solid
  assembly.py, insert.py, fit.py        parts, mates and fits; a part authored to fit between two others
  design.py, chat.py, clarify.py        a design (prompt, requirements, parts, history) and the conversation
  promote.py                            feedback becomes a rule the design keeps
  design_api.py, jobs.py, web/          the design session in the browser (FastAPI, three.js, streamed jobs)
  aero.py, frame_study.py, parked.py, snow.py   studies, through whittle
  load_study.py                         will it hold: a part's loads() through whittle's FEA and a plate check
  studies.py                            every study of a design in one list, and what each part can run
  construction.py, materials.py         what a part is built from: weight, balance, bill of materials
  cutplan.py                            cut plans (through unfold-to-sheets) and tube end cuts
  scorecard.py, release.py              the scorecard and the build package
tests/                                  the suite (pytest)
examples/                               specs, assemblies and the corner-leg machine
specs/                                  design specs
pm/                                     the work log and demo log, and the board's history
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Open work is in [GitHub issues](https://github.com/greentheo/caliper/issues);
issue titles keep a `CALI-N` id, and commits name both (`CALI-48 (#4): …`).

## License

Caliper is licensed under the [Apache License 2.0](LICENSE). Its optional tools carry their own licences:
whittle (MIT) and unfold-to-sheets (Apache-2.0).
