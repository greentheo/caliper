# Caliper work log

One file per entry, in [`log/`](log/). A PR adds a new file and never edits this one, so PRs don't conflict on the log.

- **Name:** `pm/log/YYYY-MM-DD-HHMM-cali-N-short-title.md`. The time only sorts entries within a day; entries moved here on
  2026-11-09 use a counter in its place.
- **Contents:** `### YYYY-MM-DD · CALI-N (#issue) · title`, then what changed and the tests. `git log` has the commit.
- **Read it, newest first:** `make log`.
