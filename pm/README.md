# Caliper project management (lightweight, .md-based)

A deliberately small substitute for Linear. Three artifacts, plain Markdown, version-controlled with the code so task state and the diff that satisfied it live together.

## The artifacts

| File | Role | Analogy |
|---|---|---|
| [`BOARD.md`](BOARD.md) | Kanban: every task as a one-line card under **Backlog / In Progress / Done**. | Linear board |
| [`TASKS.md`](TASKS.md) | The "issues" — full acceptance criteria, notes, and dependencies per task id. | Linear issue detail |
| [`LOG.md`](LOG.md) | Append-only, dated record of what shipped, with commit hashes and measurements. | Standup / changelog |

## Conventions

- **Task ids** are `CALI-N`, matching the design spec's seed backlog (§11).
- A task lives in exactly one BOARD column at a time. Moving it = cut the line, paste under the new heading.
- **Definition of done:** acceptance criteria in `TASKS.md` met, tests green (`pytest`), and a `LOG.md` entry written with the commit hash.
- Every meaningful change is a local git commit referencing the task: `CALI-3: evaluator parses assert exprs`.
- When you pick up work: move the card to **In Progress**, set yourself as owner, then code.
- When you finish: move to **Done** with the date, append a `LOG.md` entry, commit.

## Workflow loop (how a task flows)

```
pick from Backlog ──► move to In Progress ──► code + tests ──► pytest green
       ▲                                                            │
       │                                                            ▼
   next task  ◄──── append LOG.md + commit  ◄──── move to Done ◄── review (nightshift/)
```

The `nightshift/` scaffolding automates the right edge of that loop: run the iteration, run the
regression guard, and (later) an autonomous review pass — see [`../nightshift/README.md`](../nightshift/README.md).
