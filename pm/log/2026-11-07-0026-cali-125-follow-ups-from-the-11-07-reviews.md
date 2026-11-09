### 2026-11-07 · CALI-125 (#148) · Follow-ups from the 11/07 reviews
- **#140's survivor:** a part that builds, one rule kept and one whose probe errors: the erroring one is a fail with
  what went wrong ("lip_ratio: min_wall / 0 >= 1, not measured: ZeroDivisionError: …"), and the card leads with it.
  Pinned; the mutant (an error's own status to `verdicts.check`) fails it.
- **#135's nit:** Build it's reply log line logs the result's `ok` (a measurement that threw: False), not `not failed`.
- **#106's two survivors:** from a real older middle-only run (the reviewer's kid stool, changed since), `measured`
  carries `strength.last.edge` and the design card says "…, checked in the middle only · v2 not checked yet."; and
  `middle_only`'s fallback: an unstamped run is judged by the part as it is now (no edge foot: middle only; with
  one: not), a stamped one by its stamp. Each mutant (the edge dropped in `measured`, no fallback) fails its pin.
- The sheet's grain came out (the foreman's call: a designer could write it to get a greener verdict, and the cut
  list never tells the maker): it's #150 (CALI-126), with an assumed grain as advice and a stated one on the cut list.
- Tests: test_followups (3), test_build_plan (the logged ok). Each fails without its change.
