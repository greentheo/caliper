### 2026-11-11 · CALI-152 (#213) · A safety is cut toward safe before anything compares it

Some producers rounded a safety to two places before comparing it with the limit, so a true 1.995 against 2 was stored as 2.0 and read "holds". This is the root of what #208 fixes in the readers. Every producer that makes a verdict now stores its safety with `verdicts.cut`, which keeps two places and cuts toward safe, never rounding up. That covers the FEA, the plate, beam and ring checks and each thickness they try, a holed panel and a lightening station, the frame's designs, members and walls, a snow element, tipping, and a parked floor. A guard test fails on any `safety…: round(…)` in the producers.

Before and after, re-run on fresh copies:
- Sample stool: 3.11, plate, holds, before and after.
- Bar stool (`i-want`): 1.68 → 1.67, FEA, fails before and after.
- `i-want-2`: 0.98, fails, before and after.

No verdict moved. A number moves only where its third place was 5 or more, and it moves down by 0.01. The whole suite is CI's.
