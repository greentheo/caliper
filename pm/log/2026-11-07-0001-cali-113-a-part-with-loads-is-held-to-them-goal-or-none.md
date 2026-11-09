### 2026-11-07 · CALI-113 (#115) · A part with loads() is held to them, goal or none
- **Rule 6, found in #106's re-check:** a design whose parts have `loads()` but whose `scorecard.yaml` has no strength
  goal released "ready to cut" on a strength ✗. Only "your shop can make it" was scored. It hits designs made
  without goals: no key, older ones, a hand-made `scorecard.yaml`.
- **The scorecard now adds an implicit check** when no binding goal names strength: "holds what its loads say, at
  its factor (from its loads)", `strength.safety >=` the runs' own `min_safety`, `source: implicit`. It goes through
  the same rules as a stated goal:
  - a ✗ is a fail, so not ready;
  - "not trusted" (#96) and "not resolved" (#110) count as unknown, so not ready;
  - a strength check that couldn't run counts as unknown;
  - #106's middle-only `edge` applies once it's in `main`.
- **A stated strength goal isn't doubled.** A proposed one doesn't bind, so the implicit check still stands beside it.
- **Old designs** get the check the next time they're scored.
- Tests: `tests/test_implicit_strength.py` (the goal-less test stool at ✗ 1.46×: fail, not ready, and the book says
  why; light: pass and ready; a stated goal: no doubling). On main there's no implicit check at all. CI is the full
  run.
