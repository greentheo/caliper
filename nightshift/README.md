# nightshift/ — local loop + review + regression guard

Adopted from [ai-night-shift](https://github.com/JudyaiLab/ai-night-shift), pared down to what Caliper needs **right now**: the agent-loop conventions and a test/review guard, wired into this repo — **without** the cron daemon or autonomous overnight runs. Nothing here touches your system or schedules anything; everything is run on demand.

When we're ready to actually let it run unattended, the path is: point `loop.sh` at a real agent invocation and schedule `wrapper.sh` via cron. The structure below mirrors the upstream so that's a small step, not a rewrite.

## What maps to what

| ai-night-shift | Caliper equivalent | Status |
|---|---|---|
| `night_shift.sh` (looping agent) | [`loop.sh`](loop.sh) — one bounded dev iteration | local, on-demand |
| reviewing agent | [`review.sh`](review.sh) — pytest + ruff + diff summary | the regression guard |
| `night_chat.md` (shared log) | [`../pm/LOG.md`](../pm/LOG.md) | active |
| `bot_inbox` (task queue) | [`../pm/BOARD.md`](../pm/BOARD.md) + [`TASKS.md`](../pm/TASKS.md) | active |
| `plugins/` (pre/post hooks) | [`hooks/`](hooks/) | `regression_guard.sh` |
| `prompt_template.txt` (autonomy rules) | [`prompt_template.md`](prompt_template.md) | for future autonomous runs |
| cron via `install.sh` / `wrapper.sh` | _deferred_ — no cron yet | off |

## Commands (via the repo `Makefile`)

```bash
make test      # regression guard: pytest only
make review    # full guard before a commit: pytest + ruff + git diff --stat
make loop      # one bounded dev iteration: show board, run guard, surface next task
make board     # print the current kanban
```

## Regression guard

`hooks/regression_guard.sh` runs the test suite and fails loudly on any regression. It's the
"guard against code regressions" piece: run it before every commit (`make review` does), and it's
the natural place to gate an autonomous loop later (a red guard halts the loop instead of committing).

## Autonomy rules

[`prompt_template.md`](prompt_template.md) carries the upstream's hard autonomy rules (never wait for
confirmation, no interactive commands, bounded retries) for the day we drive `loop.sh` with a real
agent. Until then it's documentation of how the loop should behave.
