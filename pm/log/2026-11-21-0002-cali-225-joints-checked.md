### 2026-11-21 · CALI-225 (#383) · a joint the FEA read is checked; what nothing read is said, the same everywhere

caliper-ui's tester walk, on step-stool-5:
- "holds, 19 joints not checked by hand" was green and ✓;
- the design's view showed ✓ where the part's own view of the same card showed !;
- Things to fix read "✓ nothing measured wrong" beside it.

The foreman's rule. Parts 1, 3 and 4 are built. Part 2 waits on Theo.

**1. A joint the FEA read counts as checked** (`verdicts.checked`).
- **What counts:** a row's hand number, or its FEA reading, unless that's unread.
- **On a load path the hand rule can't follow,** the badge counts only the joints nothing read, `n` less those
  checked. None left, no note.
- **The FEA's own row**, for a joint the hand rule had none for, says "checked by the FEA: …" once. It used to say "not
  checked by hand; by the FEA: …".

**2. Not built, behind one switch.** A pass resting on joints nothing checked reading "not checked" reverses Theo's
answer to #222's question 1 ("✓ with a note for joints"), so it waits on his word.
- **The switch:** `verdicts.JOINT_CAP`, flipped from "holds" to "unchecked". `joint_capped` takes a close pass with it.
- **Pinned both ways:**
  - as it stands, ✓ with its note;
  - flipped, the case, the run, a close case, the goal and the summary all read "not checked".
- Glued trim alone follows his call for joints.

**3. The two views read alike.** It wasn't the joints: both read them the same, ✓ with the note. The part's card had a
line the design's lacked: "Not checked yet for a seat: leaning back …; buckling of the legs", in amber.
`answers.seat_unchecked` gives both cards that list, naming the part when there's more than one. On a copy of
step-stool-5 both cards now read amber, line for line.

**4. Things to fix lists the joints nothing checked.**
- **The row:** "19 joints not checked: …", marked `measured: False`, `badge: "not checked"` (as caliper-ui's #387 marks
  a stale check), so never "nothing measured wrong" beside it.
- **Its fix:** say how each is made in its JOINTS entry (glue, screws, a block), so the check can read it.
- None where every joint is checked.
- **It follows the switch.** The fix list already says these joints as a known limit (#318: "a known limit, never a
  row"). While a pass on them stays ✓ with its note, they stay that limit. Flipped, they become this row, and the limit
  goes. Said once either way.

**My code was wrong the first time.** The row went in unconditionally, beside the limit, and the full suite caught it:
33 fix-list tests found a row where #318 pins a known limit. The tests were right. The row now sits behind the same
switch. (The 34th red, `test_plan_groups`'s dropped floor, is main's own red that #397 fixed.)

**On step-stool-5 v16 itself:** its load path can't be followed (n 19), and the FEA read none of its joints. All 17
placed ones bond in the FEA. So part 1 changes nothing there. Its card says "19 joints not checked by hand", and
Things to fix keeps it a known limit until the switch flips.

**Pinned** (`tests/test_joints_checked.py`): every part above. **Fail first:** 5 of 6 failed on main. The sixth, ✓ with
its note as Theo's answer stands, passes on main by design.

**Mutants** (each anchor once, scratch copy), all 8 caught:
1. the chain counting every joint;
2. the FEA's reading not a check;
3. a close pass ignoring the switch;
4. the design's card leaving the seat out;
5. the row counted as measured;
6. the FEA's row saying "not checked by hand";
7. the row ignoring the switch;
8. the limit doubling the row.
