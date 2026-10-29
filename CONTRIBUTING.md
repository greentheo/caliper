# Contributing to Caliper

Thanks for looking. Caliper is run like a small engineering shop: work starts as an issue with acceptance
criteria, lands with tests, and leaves a note in the work log saying what changed and how to try it.

## Set up

Follow [Install](README.md#install) in the README, including `make tools` if you'll touch studies or cut
plans. Then:

```bash
make test       # the suite (pytest); CI runs the same on every PR
make review     # the suite, ruff, and a summary of your diff
make serve      # the design session at http://127.0.0.1:8000
```

The webapp is plain FastAPI with no front-end build: `src/caliper/web/static/` is served as is. After
changing a `.js` or `.css` file, bump its `?v=N` in `index.html` so browsers don't keep the old one.
After changing Python, restart the server.

## Issues

- Every task is an issue whose title starts with a `CALI-N` id: `CALI-48 · The shop: …`. A new issue takes
  the highest id in use plus one.
- Milestones say when (V1, M6, M5); labels say how much it matters (P0–P2) and where it lives
  (`area:author`, `area:studies`, `area:make`, `area:app`, `area:ui`, `area:measure`).
- The body says why, and what "done" means in terms someone can check.

## Changes

- Work on a branch and open a PR into `main`. A PR that finishes an issue says `Closes #N`.
- Commit messages name the task and its issue: `CALI-48 (#4): check plate thickness against the table`.
- **Done** means:
  - the issue's acceptance criteria are met;
  - new behaviour has a test, and CI is green;
  - [`pm/LOG.md`](pm/LOG.md) has an entry (newest first) with what changed, the numbers, and the commit;
  - [`pm/DEMO.md`](pm/DEMO.md) says how to try it.
- Match the code around you: its naming, its comment density, and docstrings that explain why. Ruff is set
  to a line length of 100.

## The optional tools

whittle (studies) and unfold-to-sheets (cut plans) are separate repositories. `make tools` installs them at
the commits pinned in the `Makefile` (`WHITTLE_REF`, `UNFOLD_REF`); bump a pin on purpose, in its own commit,
and let CI prove it. Tests that need a tool skip when it's missing.

To work on one alongside Caliper, use your own checkout: install whittle editable
(`pip install -e ../whittle`), and point Caliper at your unfold-to-sheets with `CALIPER_UNFOLD_DIR` or a
symlink at `vendor/unfold-to-sheets`. `make tools` leaves both alone.

## Part scripts

A design's parts are CadQuery scripts with their key numbers in a module-level `PARAMS` dict and a
`build(params)` that merges overrides, so studies can search them and write the numbers back. A part can
also declare what the studies and cut plans read: `members()` and `supports()` for a frame,
`BUILD` and `construction()` for what it's built from, `shell()`, `keeps()`, `jacks()` and others. These
are documented as part of [#1](https://github.com/greentheo/caliper/issues/1); until then, the scripts in
`tests/test_construction.py`, `test_frame_study.py`, `test_parked.py` and `test_snow.py` are the working
examples.

## Generated code

Caliper runs the Python that Claude writes, in a separate process with a timeout. That's protection
against runaway or buggy scripts, not a security sandbox. Don't open designs from people you don't trust,
and report anything that looks like a way out of that process privately (the repository's **Security** tab →
*Report a vulnerability*) rather than in a public issue.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
