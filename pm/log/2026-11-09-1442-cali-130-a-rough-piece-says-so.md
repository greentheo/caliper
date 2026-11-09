### 2026-11-09 · CALI-130 (#160) · One unsliced piece gives its own reason, and one slicer timeout doesn't stick
On Theo's stool the card read "about 220.6 h (a rough guess; the slicer couldn't work it out: PrusaSlicer, default
profile…)": a success label given as the reason for a failure, and it stayed until the server restarted.
- **The group reads its roughest piece:** `from` and `trust` come from a piece that was only guessed, and the group has
  `rough`, how many. The card says "about 12.5 h (1 of 2 pieces is a rough guess: the slicer timed out)". The build book
  prints `from`, so it's right there too, including for a caller that waits, whose rough pieces have no failure mark.
- **A remembered failure expires** after 10 minutes (`printing.RETRY_AFTER`). The next ask starts one more background
  try, once however often it's asked, and keeps showing the rough number meanwhile rather than going back to "working".
  A success replaces it; another failure waits another 10 minutes.
- **The 180 s limit starts with its own slicer.** That was already so (the worker applies it); now it's said and pinned.
- Tests: tests/test_slicer_reason.py (11, stubbed). Seven mutants each fail.
