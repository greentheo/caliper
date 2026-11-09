### 2026-11-07 · CALI-98 (#86) · A seat's load cases, and will it tip over
From Theo's first bar stool run: its designer wrote one case ("250 lb person seated", factor 1.5) and the card read ✓.
- **The designer's guide gets the load cases by kind of thing** (`part_scripts.md`): a step or tread, a seat (sitting,
  the front edge, leaning back, climbing on, tipping over), a shelf or top, a step stool; factor 2 for stepping or
  jumping, 1 for a load that sits there or a standard's test load. With a seat's four cases as an example.
- **The values are cited, through the engineering brief on #42 (section 2):** tipping, EN 1022:2005/2018 and BIFMA
  X5.1's front stability (600 N placed 60 mm in from the seat's edge, 20 N sideways at seat height); the front edge and
  leaning back, EN 12520 / EN 1728 (1,300 N 100 mm in; 1,000 N with 400 N front to back or 300 N sideways); a step
  stool, EN 14183 (150 kg). **NEEDS ENGINEER CHECK** on every value, in the code, the guide's table and the card: these
  can't be checked here against the standards' own texts.
- **A tip-over check, statics, not FEA** (`tipping.py`): a load with `"tip": True` is taken about the edge of the
  part's footprint (the convex hull of where it meets the floor) it would go over: its own weight at its centre of
  gravity and the case's downward push against the sideways one. Its verdict is `verdicts.meets` (one verdict, #132);
  a case that can't be checked (no weight, no base, no sideways push) is waiting, never a pass. The FEA leaves tip
  cases out (`load_study.prepare`).
- **The card says it:** "Won't tip when someone sits on the front edge and leans, 2.92 times over." or "Tips …: only
  0.18 times over, and it needs 1; the load alone tips it, before any push.", then "The guide's tipping pushes are EN
  1022 / BIFMA X5.1's, as Caliper's engineering brief cites them: not yet checked by an engineer.", and for a seat,
  what nobody checked: "Not checked yet for a seat: leaning back …; sitting on the front edge; buckling of the legs."
  A step stool is stood on, not sat on: its cases are a step's.
- Hand-worked: the bar stool (18 in base, seat 29 in up, 14 in seat, 10 lb): restoring 76,648.7 N·mm, overturning
  14,732, 5.2 times over, goes over at about 104 N (23 lb); a narrow stool (8 in base, 30 in): 0.18, the front-edge
  load lands outside its base. A bar stool written to the guide, through a stubbed designer: its four cases declared,
  2.92 times over.
- Not done: the live first run of the bar stool sentence (Theo's key, one run; his word).
- Tests: tests/test_tipping.py (10; they can't import `tipping` without it).
- **#141 review:** the caveat is on each tipping line itself ("…2.92 times over (EN 1022's push as our brief cites
  it; not yet checked by an engineer)"), not a line apart. A way it could tip that no case pushes, where its base is no
  wider, is said (`tipping.undeclared_ways`): the guide's bar stool, on a square base and pushed only forward, reads
  "Not checked yet: tipping sideways (no push is declared that way, and its base is no wider that way)"; the box stool,
  wider side to side, doesn't. Pinned: 0.8 against a factor of 1 tips, and the same stool raised 50 mm (its loads
  with it) tips the same (the floor is where it stands; a floor at z 0 fails it). Merged main (#139).
- **#141 review, round 2:** `check()`'s own factor is pinned (a base 10.13 in wide, about 0.8 times over: it tips against a factor of 1 and holds against 0.7, from `check()` itself), and so is "tipping front to back" (a sideways push on a square base).
