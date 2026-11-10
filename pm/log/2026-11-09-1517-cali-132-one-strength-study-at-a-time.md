### 2026-11-09 · CALI-132 (#163) · One strength study at a time, and a waiting one says so
Found reviewing #159: a Lighten beside a running carve read 0.17x to 0.7x against 3.11x alone, stopped at step 0, and said
nothing. The cause wasn't found; three different low numbers looks like a race, and a race could read high.
- **Strength studies take turns** (`caliper.one_study`): `load_study`, `carve`, `lighten` and `frame_study`, across designs, in one
  process. Re-entrant, so a study that starts another is one study. A job that has to wait says "Waiting for another
  strength study on this server to finish", naming no one's design. A carve can be cancelled while it waits.
- A long carve now makes a strength check wait for it. Workers went from 4 to 8, so a chat isn't stuck behind waiting
  studies.
- Not gated: the drag study (`aero`), which is a separate solver. Whether it shares whatever went wrong isn't known.
- Tests: tests/test_one_study.py (22, stubbed).
- **#169 review:** a study that waited now reads the design again before it starts, in place, so a part revised during the wait is studied as it now is and its record's version and number agree. Pictures, gussets, `analyse` and the parked cases take turns too. A waiting strength check or Lighten can be cancelled (a Cancel while it waits), and the scorecard and pictures say they're waiting.
