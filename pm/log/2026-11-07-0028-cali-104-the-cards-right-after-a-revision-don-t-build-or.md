### 2026-11-07 · CALI-104 (#97) · The cards right after a revision don't build or slice the part again
Measured first, on copies of Theo's bar stool (v7) and step stool at main: warm cards were already under #97's 2 s
(1.2–1.5 s, 0.3 s). The wait the operator feels is the first draw after a revision: the cards built the part again
(6 s; the revision had just built it in its own sandbox) and sliced its printed pieces again (the slicer memo keys on
the shape).
- **A revision's own build is its version's** (`DesignStore.write_part(built=…)`, `assembly.offer`): kept for the file
  it wrote, by its path, this write's time and the script's hash, checked against the file's text, so it can never
  serve another version's shape; only a build with no params (as the cards build), of the exact text written, not a
  carved one; a failed revision keeps nothing. The chat's refine and author, the by-hand number (#108) and the
  skeleton's drive (#143) hand theirs over. The mesh is the same one a fresh build gives (pinned equal).
- **The slicer off the card's path** (`printing.estimate(wait=False)`, `making.plan(wait=False)`): a printed piece not
  sliced yet is sliced in the background; the card says "Print it in PETG: 3 pieces; print time: working it out…",
  a print-time goal "print time: working it out…" (never a number, never ✓), and the page asks again until it's in.
  The scorecard, the release and the making panel still wait for the real number.
- **Timings** (the bar stool, main → here): a cold open 20.1 → 11.9 s; the cards after a revision that changes its
  shape (seat_dia +2%) 11.4 → 3.9 s, the print time filled in a second later; warm unchanged (1.2–1.7 s). The step
  stool after a revision 3.1 → 1.4 s. What's left cold is the build (7 s, once per version per process) and the
  consistency check's rays and thinnest wall (3 s).
- Tests: tests/test_cards_speed.py (9: the revision's build is the cards', the same mesh as a fresh build, never
  another version's, nothing kept but a good build of the exact script, a refine builds its part once; the slicer
  never holds a card, the cards say working it out and a print goal waits, the page asks again). All fail at main.
- **#152 review:** a background slice that fails or hangs is remembered per piece and said once: the rough number
  marked "(a rough guess; the slicer couldn't work it out: the slicer timed out)", or, if it crashed, "print time: the
  slicer couldn't work it out: …" with no total (a print goal says so, never a number); the page stops asking. It
  starts once however often the page asks (pinned: 5 asks, 1 start). One slicer worker, so a part's pieces slice in
  turn; a background slice gives up at 180 s (a waiting caller keeps 600 s, and still slices again, #140). An offer
  whose file was rewritten in the same tick with other text is never taken (pinned).
