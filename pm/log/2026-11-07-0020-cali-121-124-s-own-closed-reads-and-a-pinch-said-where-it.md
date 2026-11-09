### 2026-11-07 · CALI-121 (#134 review, with main's #124) · #124's own closed reads, and a pinch said where it is
- **#124's three reads in `carve.py`** (`_closed`'s two, and `adopt`'s check of the STL as it reads back) go through
  `measure.closed()`; `closed(m, volume=True)` adds the winding (`is_volume`), so `with_printed`'s raw `is_volume`
  goes too. The guard passes with no new `# raw:`.
- **`open_near` places a pinch:** it takes every edge with other than two faces (an opening has one, a pinch four),
  so a pinch reads "near z 5 mm", not the part's whole height. `with_printed` says where: "not checked: its shape
  isn't closed near z …".
- **The whittle bridge already merged on load:** `_mesh_of` reads the STL with trimesh's default `process=True`,
  which merges vertices, so a pinch already read open there. Its switch to `closed()` is belt and braces, not a fix.
- **The review's two survivors are pinned:** the build reply carries the ⚠ line (through `_compose`), and a pinched
  printed part isn't weighed. Fail-first: 4 of the 8 fail without this (the guard, the pinch's place, the reply, the
  weight).
- **`test_mixed`'s carve-down runs in parallel again:** its `serial` mark (CALI-114) waited on #105's watertight adopt,
  which #124 landed. CI's serial step allows none (`|| test $? -eq 5`).
- **#134 review, round 2:** `closed(volume=True)` pinned with an inside-out box: watertight and closed, but its volume reads negative, so it's no solid to weigh (`with_printed` says so).
