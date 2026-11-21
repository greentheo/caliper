### 2026-11-20 · CALI-224 (#382) · a Lighten weighs every step against the part as it is now

Found on caliper-ui's tester walk, on a copy of step-stool-5. v16, already lightened (17 holes, 5.59 lb lighter), was
offered "5.23 lb lighter" by a second Lighten. Use it made it 0.36 lb heavier: 19.2 to 19.5 lb. Using a step replaces
the part's holes with the step's, and every step was weighed from the part with no holes.

**The fix** (`lighten.py`):
- **What the part saves now:** `holes_now_lb` weighs the part's own lightening holes, its `HOLES` (pictures aside, which
  Use it keeps), each in its sheet's thickness and its own material.
- **Every step against now:** `against_now` subtracts that from every step's `saved_lb`, the thinner-sheet rows
  included, after those are worked out from the bare part. The record keeps `now_lb`.
- **A step that would put weight back reads below zero.** `use_step.choose` never offers under its floor (at least a
  quarter pound), so it's never an offer.
- **An older run of this version** (no `now_lb`) is weighed against now when it's read back. Where its holes can't be
  read, nothing of it is offered.
- **Everything that says "lighter" reads against now:**
  - the studies' line ("nothing lighter holds" at or below zero, never "up to −0.36 lb");
  - the page's lead line (`best.saved_lb > 0`);
  - the step's history line ("lighter than it was");
  - the study's last word ("lighter than now").

**Pinned** (`tests/test_lighten_vs_now.py`):
- **A second Lighten** on #346's three-load box, after using a holding step with holes:
  - `now_lb` is what those holes saved;
  - its step 0 (no holes) reads that much below zero;
  - whatever is offered, used, makes the part that much lighter.
- **The issue's own numbers** (5.59 lb now, a step of 5.23): −0.36, and never an offer.
- **An older run** is read against now.
- **The studies' line** never says lighter for a step at or below now.
- **A picture** cut into a panel isn't a lightening hole.

**Fail first, as behaviour:** on main the new tests can't even import `holes_now_lb`, which proves nothing about the
bug. So I ran the same second Lighten on main's code and on this:

| the second Lighten's steps | main | this |
|---|---|---|
| step 0, no holes | 0.0 lb lighter | −1.16 |
| step 1, 5 holes | **0.4 lb lighter** | −0.76 |
| thinner rows | 0.64, 0.88, 1.0 | −0.52, −0.28, −0.16 |

The part's own holes saved 1.16 lb. On main, "up to 0.4 lb lighter" was 0.76 lb heavier than the part as it was. This
box got no button either way, since none clears the floor, but main's table and line said lighter.

**One test of mine was wrong:** I first took the second Lighten's step 0 for the part as it is. It cuts no hole at all,
so used it would fill the part's holes back in, and it reads −1.16 against now. That's right. The test now says so.

**Mutants** (each anchor once, scratch copy), all 5 caught:
1. the study's steps not against now;
2. pictures counted as lightening holes;
3. an older run read from the bare part;
4. the studies' line saying lighter at or below zero;
5. a hole weighed at its sheet's thickness, not its depth.

The fifth survived at first. Lighten writes each hole's depth as its sheet's thickness, so the two agree on its own
holes. But a hand-written hole can be a pocket, so a hole now weighs as deep as it goes (capped at its sheet), pinned
with one half as deep.

**Area tests:** green at `-n 4` (the Lighten files, the studies' line, Make it better, the step previews). **Full suite:
CI.**
