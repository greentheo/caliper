### 2026-10-29 · Open source: issues, licence, CI, install for a stranger (CALI-60, #5)
**Try it:**
- Open work: https://github.com/greentheo/caliper/issues (V1 is milestone 1). Each title starts with its
  CALI id. `pm/BOARD.md` is history now, with a map from old cards to issues.
- CI: every PR runs the suite on GitHub (PR #25's first run: 447 passed, none skipped).
- `make tools` installs the optional tools at pinned commits (whittle into the env, unfold-to-sheets into
  `vendor/`). On your machine it says both are your own checkouts and leaves them alone (`vendor/` is a link
  to `~/githubrepo/game-dev/unfold-to-sheets`).
- The README's Install section is the stranger's path: clone, micromamba, `make install`, `make tools`,
  `.env`, `make test`. CONTRIBUTING.md covers issues, commits, what "done" means, and the optional tools.
