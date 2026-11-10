### 2026-11-10 · CALI-144 (#184) · A build package behind a strength check uses that check

The scorecard looked for a strength run of this version before it took its turn, found none yet, and ran the same check again straight after the first finished. It now takes its turn first and looks again, inside the turn. Several minutes of machine saved for nothing lost: a run of an older version still doesn't count, and Cancel while it waits still stops it. Tests: tests/test_one_check.py. The whole suite is CI's.

From the review: a package that waited through a revision came out labelled v1 with v2's shape and v1's strength. If any part changes during the wait, the score starts again from the top against what's there now, and the package does too, so the labels, the files, the source and the strength row name one version. A design that keeps changing stops and says so.
