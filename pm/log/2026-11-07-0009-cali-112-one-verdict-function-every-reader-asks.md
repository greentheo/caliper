### 2026-11-07 · CALI-112 (#114) · One verdict function every reader asks
- **`verdicts.py`:** kinds worst first (`fails`, `untrusted`, `unchecked`, `unresolved`, `edge`, `stale`,
  `waiting`, `holds`), each with a status, a word and `counts_as_pass`; `case`, `run`, `goal`, `meets`, `station`,
  `check`, `summary`, `of`. A new kind is one entry. Precedence as the PRs settled it: a ✗ stays a ✗, then not
  trusted, not resolved, middle only, older version, waiting.
- **Every reader asks it** (the audit is in the PR): the part and design cards, the make card, the scorecard's
  statuses, the book's header, its Will it hold? row and its marks, the kids' book, Studies, the chat's facts, the
  picture reply and the chat's ok for it, the history line, the study's closing message, and the page's badges,
  run word, history line and stress bar (from `design_state`'s `verdict` on every run, case and history line).
  Producers and searches carry `# producer` / `# search`.
- **What the audit found, now fixed:** a fail on a filled-in block read "not trusted" on the scorecard (✗ on the card);
  the kids' book said "It should hold …, 1.2 times over" for a stool that fails; the history read "holds" for a check
  on a filled-in block; "✓ I cut a T. rex" led a ✗; Studies showed a card with checks still unknown green; a design
  with no checks read "Ready to cut — 0 of 0".
- `tests/test_verdicts.py` (37; can't import on main): two grep guards (Python and the page), every kind through
  every reader (cards, book row, kids' book, Studies, picture reply, page badges in node), the precedence, the summary,
  `goal`. Tests that read the old fields read the verdict now. design.js v=67.
- **#132 review (the foreman's sweep), A–D:** a design's verdict never leaves a part out (a part unchecked, older or
  errored is that: `measured()`, the scorecard, the kids' book, frame runs now record their version); `stale` is
  produced wherever a run isn't the part's version (badges, the part card, the chat's facts, the make card, Studies
  rows, releases via `verdicts.release`); carve steps (`carve_step`: the whole part and filled-in too), lightening
  steps (`lighten_step`: an estimate is its own kind), the plate check's rows, the first reply (worst first), a part's
  rules (`_rules_line`), trials (held but short), `promote`'s `holds_now` (unknown by default, `verdicts.rule`) and
  app.js's badge all ask the verdict; goals compare in `verdicts.compare`. Both guards widened (`< min_safety`,
  `>= limit`/`lim`, `ready`, `best`, `holds_now`; every `.holds`, `whole_holds`, `safety_across >=` in design.js and
  app.js): on the pre-rework head both fail, with all 13 of `tests/test_verdicts_sweep.py`.
- **#132 review, round 2:** the release panel reads `verdicts.release` (ready as made and for the parts as they are,
  its own reason when not); a revision's history stores its report's verdict (`verdicts.report`): a fail only with a
  failure, pass plus a waiting check is "not all checked", only waiting or nothing is "nothing checked yet", never
  red; older records read through `verdicts.history`. `summary(None)` and `meets(…, None)` wait; `release()` keeps
  its own reason; `to_text` and the CLI say ALL PASS only with nothing waiting; lighten's two searches marked as such.
  Both guards cover `ready` and `all_pass` now.
- **Merged with main's #124:** a carved step marked `closed: False` (its part doesn't close up) is never a pass:
  `verdicts.station` reads it "not checked", with its why, so `carve_step`, the step offered (`_offer`, and the
  lightest on a cancel), the chart dot and **Use this step** (off) all say so from the one verdict.
