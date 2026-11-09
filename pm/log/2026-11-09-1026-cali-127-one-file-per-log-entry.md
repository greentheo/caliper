### 2026-11-09 · CALI-127 (#154) · One file per log entry
- **Why:** every PR added its entry at the top of `pm/LOG.md` and `pm/DEMO.md`, so every merge made every other open PR
  conflict: about 15 extra merge-forwards and CI rounds on 11-06/07. Theo's call.
- **Now:** each entry is its own file in `pm/log/` or `pm/demo/`, named `YYYY-MM-DD-HHMM-cali-N-short-title.md`. `pm/LOG.md`
  is a static pointer, `pm/DEMO.md` keeps its guide sections, and `make log` / `make demo-log` print the entries newest first.
- **Moved:** 112 log entries and 83 demo entries, byte for byte (checked by the script that split them). Within a day their
  names use a counter for the time, so the old order holds.
- **Guard:** `tests/test_pm_log.py`: no dated entry in the shared files, and each entry file's name matches its heading's date.
