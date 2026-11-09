### 2026-11-07 · CALI-121 (#134 follow-up) · The carve-through-the-API test waits 1,500 s for its job, not 900
- `test_mixed::test_carving_through_the_api` waits for its carve job before it reads the run. On a loaded machine the
  job took 790 s on its own and over 900 s twice beside two other test runs (#134's merge-forward), so the test timed
  out with the job still running. A CI runner varies as much: the wait is 1,500 s, which a carve that hangs still
  fails. No code changed.
