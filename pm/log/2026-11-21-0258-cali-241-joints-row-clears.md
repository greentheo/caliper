### 2026-11-21 · CALI-241 (#413) · a joint nothing checked is named, with why, and offered only a fix the check credits

From caliper-reviewer's review of #407 (CALI-225, #383), filed at the foreman's ask, ahead of #17 slice E. It has to land
before `JOINT_CAP` flips. Stacked on #407 (3423be7).

**The gap.** On step-stool-5, flipped, the "not checked" row's one fix was "say how each is made in its JOINTS entry".
That can't clear it:
- 11 of its 17 placed joints already had entries;
- the reviewer added the other 6 on a copy, and a fresh check still read "19 joints not checked".

Its joints are unread because the FEA waives a pull their fixings can't give, and the hand rule can't follow its load
path. The row didn't name them either.

**Why nothing clears it today.** The capacity table credits no pull at all at an edge or end grain:
`WITHDRAW_EDGE_LB` and `GLUE_EDGE_PSI` are both 0 (NDS 2018 §12.2.2.3; the Wood Handbook; Theo's #301 decisions 2 and
3). So no `JOINTS` entry, glue or screw count makes the check credit that pull.

**The foreman's rule** (as for the glue block): offer only what the check credits.
- **A fixing the table credits** for a joint's pull: its own row, the fixing named, one tick. The re-check clears it.
- **Nothing credits it:** said, and why, with no tick.

**Built:**
- **The FEA's reading keeps every joint nothing checked** (`fea_joints._open`, the case's `joints.open`). Each one is
  `{pieces, between, why}`, plus `fix` where a credited fixing clears it. The why is the reading's own:
  - a pull nothing credits;
  - can't see it;
  - a load on it;
  - hung;
  - unbalanced;
  - a through tenon;
  - a notch;
  - a dowel, which has no rule yet;
  - no force on it.
- **A credited fixing** (`fea_joints.credited`): the fewest screws that the fresh check reads past the need, with the
  pull no longer waived. A count read with the pull still waived isn't one, because the waiver isn't a check. It's said
  as `joint_check.fix_it` says it, its `JOINTS` entry to the letter.
- **Things to fix, flipped:**
  - each joint with a credited fixing is its own row, `joints_unchecked:<pieces>`, `measured: False`, badge "not
    checked", its one choice the fix list's joint screw fix (#344);
  - the rest are **one known limit** naming them, at most 3 per why and "N more", with each why: "6 joints not checked,
    by hand (…) or by the FEA, and nothing the check credits clears them yet: …".
  - Never a tick that comes back unchanged.
  - An older run with nothing named keeps the card's words, as at "holds".
- **At "holds"** nothing changes: the card's known limit, no row.
- **The count says "not checked"** (`brace_why`): it counts what neither the hand rule nor the FEA read. It's taken
  from the named list where there is one, so the card's count and the limit's agree.
- **A new FEA row starts "not checked by hand"**, as on main. Only a number makes it "checked by the FEA". A joint the
  FEA reads carrying nothing had said "checked by the FEA" while `checked()` was False.
- **Dead code removed:** fixes' `not b.get("trim")` filters. `wood_brace` never returns trim, which is why the
  reviewer's two trim mutants survived. Glued trim is said on the card (`verdicts.case`), never in the fix list; pinned.

**On step-stool-5**, flipped, the expected result is no row and one known limit, which names its joints and says no
fixing the check credits takes a pull at an edge. I didn't re-run it, since that needs a fresh check of Theo's design.
This is pinned on a synthetic part of the same shape instead: every joint declared, every pull uncredited.

**Pinned** (`tests/test_joints_row_clears.py`, 14 tests, synthetic only):
- each joint nothing checked is kept by name, with why: a pull, a through tenon, a notch, a dowel, an unbalanced
  reading;
- a joint the FEA checked isn't kept;
- **credited** (`WITHDRAW_EDGE_LB` patched to 50, as test_fea_joints does): the count is offered, its JOINTS entry
  applied clears the joint at the number offered, and one screw fewer reads short;
- more screws aren't offered where they'd pass only with the pull still waived;
- a joint the FEA gave no number isn't said checked by it;
- the count and its words;
- flipped: nothing credited is a limit naming them, never a tick; a credited one is its own row, the rest the limit;
  the case with the most is said, once;
- at "holds", as it was, a credited joint included;
- glued trim is never a joints row.

The reviewer's survivors are pinned too: the design card naming each part, and an FEA-checked row keeping its crowded
words.

**Fail first:** on #407's code, with only the three new word constants added, 8 of the first 12 new tests failed.
The other four pin what was unpinned and pass there by design: the crowded words, "holds" unchanged, glued trim, and
the card naming the part.

**Tests I changed, and why:**
- 9 pins of the count's words "N joints not checked by hand" (test_joint_check, test_joints_checked) now read "not
  checked". The words changed on purpose; the lines' own words ("not checked by hand: its load path …") stay.
- #407's flipped-row test now pins an older run's fallback. Its row moved to the new file.

**Mutants** (each anchor once, scratch copy), all 16 caught:
1. a count read with the pull still waived offered as a fix;
2. a new row starting "checked by the FEA";
3. the list keeping checked joints;
4. a credited joint's why the uncredited words;
5. an unbalanced reading keeping no list;
6. a notch said as unread;
7. a kind with no rule said as unread;
8. the count ignoring the list;
9. the count saying "by hand";
10. a credited joint getting no row;
11. the limit naming credited joints too;
12. the case with the fewest said;
13. the limit once per case;
14. rows at "holds";
15. the design card never naming the part;
16. an FEA-checked row losing its crowded words.

The first survived at first: my pull fixtures carried no shear, so a count read with the pull still waived gave no
number at all. A screwed joint whose shear passes now pins it. That was my test's gap; the code was right.

**Area tests:** green at `-n 4`: the joints files, the FEA joints, the fix list, Fix these, the joint check, verdicts,
wording, posts, strength measurement, the fix-joint flow, the part menu. **Full suite: CI.**
