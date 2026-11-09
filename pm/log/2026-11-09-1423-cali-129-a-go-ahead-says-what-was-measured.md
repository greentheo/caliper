### 2026-11-09 · CALI-129 (#158) · A go-ahead to fix a failing rule tells the designer what was measured and where
On the one live "have a go" the designer was told the rule and nothing else: `min_wall` went from 0.25 to 0.225 mm and
the volume went up 75%. It never knew where the wall was thin.
- **The instruction now carries the measurement** (`part_rules.to_fix`), taken on the version it's about to change: "the
  thinnest wall is 0.25 mm at x …, y …, z … mm in this script's coordinates; the rule needs at least 2.85 mm", and that
  `min_wall` is the thinnest material anywhere, webs between openings included. A rule with no location gives its
  measured value; a wall that can't be located still says how thin.
- **Script coordinates in mm,** with the part's placing taken out: a script doesn't know where the design put it.
- **Told to the designer only:** a location is true of this version, so the part's history and description keep the
  plain request.
- **Found on the way:** a part's measured rules were cached per version only, so a part moved in the design (same
  version) kept saying where it used to be. The cache now keys on where it sits too.
- It says *where*, not *what's there*: the measurement knows a point, not that it's "the webs between the cone's
  openings". Whether this gets the stool's wall to pass needs a live run, which waits for Theo's word after #155.
- Tests: tests/test_fix_rule_measured.py (9, stubbed). Mutants (no placing in the cache, no inverse pose, the note in the
  record, a passing rule said to fail, the location dropped) each fail.
