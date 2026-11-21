### 2026-11-21 · CALI-88 (#64, item 1 on the page) · a part's History cuts its strength number toward safe

Item 1 (#208) made the cards and replies cut a safety, never round it up to its limit, and the server stores every number
cut to two places (`verdicts.cut`). One reader on the page still rounded: the History line's strength check used
`toFixed(1)`. A check that failed at 1.96 against 2 read "strength check: fails, 2x", the very number it needed. 9.96 read
"10x", and 0.04 read "0x".

- **The fix:** it's cut to one place (1.96 → 1.9x, 9.96 → 9.9x), and under 0.1 reads "under 0.1x", as `safetyNum` says it.
- **The sweep of the page's other safety numbers:** every other place either goes through `safetyNum`/`sx` or shows
  the server's two-place cut value as it is (frame stations, carve and Lighten steps, the plate's thicknesses), which is
  never greener. Nothing else needed changing.

**Tests:** `tests/test_history_safety.py`, 6; four fail on main (1.96, 1.99, 9.96, 0.04). test_edge_foot and
test_leftovers_70, which read `historyItem`, pass.

**Mutants, 3 of 3 caught:** toFixed back; rounded (`Math.round`); 0x allowed.
