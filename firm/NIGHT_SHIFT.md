# Night shift

**Night shift turns a ready issue into a tested pull request.** Autonomous: work without asking for input,
and leave what you can't resolve as a written question on the issue rather than a guess.

Read [README.md](README.md), then the specs it lists, then [`pm/LOG.md`](../pm/LOG.md)'s last few entries
(what was just built, and why). For anything the designer writes, read
[`src/caliper/part_scripts.md`](../src/caliper/part_scripts.md): it's the designer's reference, word for word.

## Prep (once per session)

1. Work in **your own worktree**: `~/githubrepo/caliper-nightshift`, a scratch designs folder, port 8016
   (setup in [README.md](README.md#workspaces--one-checkout-per-seat)). Never touch `~/githubrepo/caliper`.
2. `git fetch`, then check out the issue's base branch (the issue names it; `main` once the stack is merged),
   `git status` clean.
3. Run the tests for the area you'll touch. If they're red before you start, tell the foreman; fix nothing
   that isn't your issue.
4. Read the foreman's notes from your last session's report, if any.

## The loop

### 1. Pick an issue
`gh issue list --label "stage: ready" --state open` — skip `in-progress` and anything whose `Blocked by:`
is still open. Bugs first, then the milestone order (V1 first). If the foreman assigned you one, take that.
Add `in-progress`, branch `cali-N-short-name`.

**If the issue isn't a spec yet** (no acceptance criteria, no test plan), don't invent one: comment what's
missing, signed, and tell the foreman.

### 2. Load context
Read every file the issue touches, fully, before changing it. Read the tests next to them. Understand the
current behaviour first; run it if you can.

### 3. Tests first
Write tests that express the acceptance criteria and **watch them fail** before you implement. Use real
shapes: a part script like the suite's fixtures (`BOX_STOOL`, `STOOL`, `MIXED`), a real run record from a
study, a real design folder (`caliper/samples/`), not structures invented from memory. A test that builds
geometry needs CadQuery (`pytest.importorskip("cadquery")`); one that runs the FEA needs whittle (coarsen it
with `VOXELS_THROUGH = 2` so it's quick).

### 4. Plan, small
The minimal diff that meets the criteria. No speculative features, no new abstractions for one use. If it
won't be reviewable in 10–20 minutes, stop and ask the foreman to split the issue.

### 5. Check the plan against the personas
Run the personas in [REVIEWER.md](REVIEWER.md#the-personas) over your plan. Fix what they'd flag before
writing code. At most three passes.

### 6. Build
One logical change at a time, matching the surrounding code's style and comment density (module docstrings
say what and why; comments name the issue that needs them). The page is plain JavaScript with no build step:
bump `?v=` on `design.js` / `design.css` in `index.html` when you change them, and `node --check` the file.
Update `src/caliper/part_scripts.md` when what a script may declare changes.

### 7. Verify — all of it, and say what you ran
```bash
export PYTHONPATH=$PWD/src            # always (README: the trap); add a whittle checkout when the pin needs it
export CALIPER_UNFOLD_DIR=<unfold-to-sheets at UNFOLD_REF>               # else the cut-plan tests skip
/opt/anaconda3/envs/caliper/bin/python -m pytest tests/test_<area>.py -rs    # while working
/opt/anaconda3/envs/caliper/bin/python -m pytest -rs                        # once, before the PR (20-40 min)
node --check src/caliper/web/static/design.js                                # when the page changed
```
For anything a person sees: run the app on 8016 with a scratch designs folder, and click through the
acceptance criteria in the browser. For anything that changes a strength verdict: run the suite's strength
fixtures before and after and put the numbers in the PR (rule 6). Read the exit status directly, not
through a pipe.

### 8. Pull request
- Commit `CALI-N (#issue): what changed and why`, ending with the `Co-Authored-By` line; push;
  `gh pr create` with the base the issue names and the title `CALI-N (#issue): <what it does>`.
- The body opens with `— night shift`, then: what changed, how you verified it (commands and results, what
  you clicked), what you could **not** verify, anything that changes a verdict or a saved design, and
  `Closes #N`. It ends with the Claude Code line.
- `pm/LOG.md` and `pm/DEMO.md` are updated in the PR (see README).
- **Never merge, never push to `main`.**
- Move the issue to `stage: review`, drop `in-progress`, and tell the foreman the PR is up.

### 9. Next
Back to 1. At most **three issues a session** — quality over count.

## Consult Socrates first when…

…the work changes a strength verdict or what the cards say a part can do, touches the owner's designs or
anything saved in a design folder, sends anything outside the machine (an API call beyond the work, an error
report, a hosted service), runs generated code in a new place, or affects what a kid sees — **and the foreman
hasn't already**. Put your scope on the issue first; Socrates won't question a message.

## When done

Comment on each issue you touched (signed): what's done, the PR, caveats. Send the foreman a short report —
completed, blocked and on what, what you'd do differently, what you filed. Then stop.

## Safety rails

- Never touch the owner's checkout (`~/githubrepo/caliper`), their designs (`designs/`), their shop
  (`~/.caliper/shop.yaml`) or their whittle and unfold-to-sheets checkouts. Tests already point the shop and
  the error log at temporary files (`tests/conftest.py`).
- Never print or commit secrets; never commit `.env`. Calls to Claude cost the owner money: tests run
  offline (`ANTHROPIC_API_KEY` unset, or an injected fake client), and a live check uses as few calls as
  it needs.
- Never force-push or rewrite `main` or another seat's branch.
- Never change what a saved design means without saying so in the PR: a part script's declarations, a run
  record's fields, `HOLES` / `CARVED`, `scorecard.yaml`. Old designs must still open.
- Generated code runs only in the sandbox (`sandbox.run_script`); never `exec` a part script in the server
  process.
