### 2026-10-29 · CALI-60 (#5) · Install for a stranger: README, CONTRIBUTING, `make tools`
- **README** rewritten for someone who isn't us: what it does (design, test, plan the build, price,
  release), honest status (#1 is the biggest gap), install with micromamba, run, the CLI, how it fits
  together, and a plain warning that Caliper runs the Python Claude writes (a worker process with a timeout,
  not a security sandbox). The Theo-machine notes (sandbox, `/opt/anaconda3`) are gone from it.
- **CONTRIBUTING.md**: setup, `make test` / `make review`, the `?v=N` and restart gotchas, issues and
  commit conventions, definition of done, the optional tools, part-script declarations (pointing at #1),
  generated code and private vulnerability reports, contributions under Apache-2.0.
- **No local paths:** `cutplan.unfold_dir()` = `$CALIPER_UNFOLD_DIR`, else `vendor/unfold-to-sheets`, else a
  checkout beside the repo (test added). The whittle hint says `make tools`. "Theo's" dropped from the
  docstrings.
- **`make tools`:** whittle and unfold-to-sheets at pinned commits (`WHITTLE_REF` 5363df5, `UNFOLD_REF`
  54e1af4); leaves an editable whittle and a symlinked `vendor/` alone (checked here; and from a scratch
  folder it clones, checks out the pin, and re-runs cleanly). CI uses it, so the pins are proven there.
- `environment.yml` gains `httpx` (the server tests need it; `requirements-pip.txt` had it). CI actions
  moved to Node 24 majors (checkout v5, setup-node v5, setup-micromamba v3).
- Tests: cut-plan + release 15 passed here; PR #25's first CI run before this commit: 447 passed, 0 skipped.
