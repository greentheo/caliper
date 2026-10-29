# Caliper project management (lightweight, .md-based)

Open work is tracked in **[GitHub issues](https://github.com/greentheo/caliper/issues)** (since 2026-10-29). The Markdown files here keep
what doesn't fit an issue tracker: the work log and the demo log, version-controlled with the code.
`BOARD.md` and `TASKS.md` are frozen as the record of M0–M6; `BOARD.md` maps each card that was still open
to its issue.

## The artifacts

| File | Role | Analogy |
|---|---|---|
| [GitHub issues](https://github.com/greentheo/caliper/issues) | Open work: one issue per task, acceptance criteria in the body, milestones and labels for priority and area. | The board |
| [`BOARD.md`](BOARD.md), [`TASKS.md`](TASKS.md) | Frozen 2026-10-29: the board and task cards for M0–M6. | Archive |
| [`LOG.md`](LOG.md) | Append-only, dated record of what shipped, with commit hashes and measurements. | Standup / changelog |
| [`DEMO.md`](DEMO.md) | Demo & testing log — current capabilities + the exact commands to try each shipped thing. | Release notes / "how to try it" |

## Conventions

- **Task ids** are `CALI-N` and stay in the issue title (`CALI-48 · The shop: …`); the next new id is the
  highest one in use plus one.
- **Definition of done:** the issue's acceptance criteria met, tests green (`pytest`, and CI on the PR), a `LOG.md`
  entry written with the commit hash, **and `DEMO.md` updated** — refresh "current capabilities" and
  add a demo-log entry with the exact command(s) the human can run to try the new work.
- Every meaningful change is a commit naming the task and its issue: `CALI-48 (#4): plasma bed check`.
  A PR that finishes one says `Closes #4`.
- When you pick up work: assign yourself the issue, then code.
- When you finish: append a `LOG.md` entry, update `DEMO.md` (capabilities + how-to-try), commit, and
  close the issue (or let the PR close it).

## Workflow loop (how a task flows)

```
pick an issue ──► assign it ──► code + tests ──► pytest green ──► PR, CI green
      ▲                                                                   │
      │                                                                   ▼
 next issue ◄── append LOG.md + update DEMO.md ◄── merge (Closes #N) ◄── review (nightshift/)
```

The `nightshift/` scaffolding automates the right edge of that loop: run the iteration, run the
regression guard, and (later) an autonomous review pass — see [`../nightshift/README.md`](../nightshift/README.md).
