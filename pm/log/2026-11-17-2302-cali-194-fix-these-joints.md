### 2026-11-17 · CALI-194 (#316) · a failing joint's fix flows into Things to fix, and Fix these makes it

Theo, deciding #344's hold: the conservative number governs (the FEA's 1.5 where it's lower), and the fix "ends up getting
passed into the 'fixes' part of the UI, this will be part of what makes our tool magical". The foreman's rule from now on:
every new red ships with its fix flowing into Things to fix. Plus caliper-reviewer's three small asks from the full review.

**What was there.** A failing FEA joint row did reach Things to fix (`joint:front rail|left side`). Its choices were the
generic "More screws where … meet", a glue block, and a dado or rabbet. None of them had a count. Worse, **a joint's screw
count couldn't be declared at all.** `marks.screws` laid screws by the joint's length (1½ in from each end, no more than
6 in apart), so step-stool-5's 6 in rail ends had 2 screws, always. A designer told "add a screw" had nothing to write
that the check would count, so Fix these could never pass the row.

**1. A `JOINTS` entry may give its own count, `"screws": N`.**
- `marks.spots(mm, n)` lays them evenly, 1½ in from each end where the joint has room, else evenly across it.
- The patterns, the cut list, the shopping list, the book and the joint check all read that one count.
- `joints.check` refuses a count that isn't a whole number of 1 or more, or that comes without "screws" in the fix.
- **Theo's call on spacing:** "default to even spacing on the joints". Any count is credited. Where they come out
  closer than `SCREW_MIN_GAP_IN`, the row says so: "4 screws 0.75 in apart in a 3 in joint: close enough to split the
  edge; consider a longer joint or a bigger screw".
- **Both distances are marked NEEDS ENGINEER CHECK in `marks.py`, with their sources:**
  - **1 in, interim:** about 6 d for a #8. For comparison, EC5's predrilled a1 = (4 + |cos α|) d is 0.66 to 0.82 in.
    Theo's to set, like the plywood's 9.7 MPa.
  - **The 1½ in end distance:** a shop layout rule from the screw marks (CALI-177), not taken from a standard.

**2. The fix-it: the fewest screws that pass, and what the joint would read.**
- `joint_check.fix_it(j, need, safety_with)` counts up from the joint's present screws until the row's own safety
  passes the bar.
- The safety at each count is the one the fresh check will read:
  - **on the FEA's side,** `fea_joints.row` is run again with the joint held by n screws, since a pull's waiver turns
    on what holds it;
  - **on the hand rule's side,** every demand the row answers to, unrounded. That is the frame's load and, on a raked
    leg's tie, the rake's thrust;
  - **the lower of the two** governs.
- **Where the screws go matters.** On a sheet's edge, the farthest screw takes the moment, so the n screws are laid
  where `marks.spots` lays them. An apron's end or a post has no screw points, so none.
- **The words:** "1 more #8 screw at the top's edge, 4 in all, would read 2.14×, past 2". The foreman's correction: no
  "or a glue block", since the capacity rule never credits one.
- **Hand rows carry it too.** Before, only the FEA's rows did.

**3. Things to fix offers only what the check credits** (`fixes._joint_choices`).
- **A screw count passes:** the one choice is the `JOINTS` entry to write, to the letter, and what the joint would read:
  `3 #8 screws where the front rail and the left side meet, 1 more: its JOINTS entry {"pieces": ["front rail", "left
  side"], "kind": "butt", "fix": ["glue", "screws"], "screws": 3}; it would read 2.28×`.
- **A row speaking for several cases** takes the count every one of them passes at.
- **Dropped:** the glue block, and "a dado or a rabbet" (capacity() credits neither: dados aren't `EDGE_KINDS`).
- **Kept by how it gives,** where no screw count helps: more bearing, the net section past a notch, and "ask it to hold
  less".

**4. caliper-reviewer's three.**
- **The statics pin's docstring** claimed a voxel read as the wrong piece leaves a residual. It doesn't: each piece's
  joints still carry exactly what reaches it, so the pin only sees voxels no piece has. It now says so (the docstring
  was wrong, the number doesn't move).
- **The hung apron's words** said "a glue line" where the apron was screwed to the top (my code). `held_by` names what's
  there: "two #8 screws and glue", "one #8 screw", "a glue line that gets no credit in a pull", "nothing that holds a pull".
- **`MIN_NODES`, `STATICS_TOL` and `DISAGREE` are pinned at their edges.** `sees` and `unbalanced_by` are split out so
  the bars are testable: 4 nodes read and 3 don't; a residual of 1% reads and 1.01% doesn't; the FEA's 125 lb against
  the hand's 100 is said and 124.9 isn't.

**5. The hung apron's waiver turns on the top joint's pull capacity, in code** (the foreman). An apron hanging from the
top is waived, its shear going round, only where what holds it to the top is credited no pull. Today that's every edge
(`WITHDRAW_EDGE_LB` is 0), so nothing moves. If a pull is ever credited there, the hang is carried by its fixings and
the apron end's shear stands, said "the front apron hangs from the top by two #8 screws and glue, which hold a pull, and
it hands 34 lb to the leg through …". Pinned with `WITHDRAW_EDGE_LB` patched to 50.

**Found on the way. My code was wrong each time, caught by the end-to-end tests:**
- The promise said 2.17× where the fresh check reads 2×: I had laid an apron end's screws as points, and the check
  gives it none.
- A box top's side said 2.7× where the check reads 2.69×: the hand demand was rounded to 0.1 lb.
- A rake tie's row overwrote the joint's row but kept the old count. Now each row keeps every demand it answers to.

**End to end** (`tests/test_fix_joint_flow.py`, real FEA, stub designer that writes only the entries its message names):
- **LEGGED** (✗ 0.5 at the front right leg's apron end): all 8 joint rows ticked, one designer message, 8 fixed. Each
  joint reads exactly what its choice said.
- **BOX_STOOL's top** (1.6 by the FEA): its four sheet-edge joints, two by the FEA and two by hand, likewise.

**On a step-stool-5 v12 copy** (scratch, not committed):
- **Before:** stepping on the front edge reads ✗ 1.5 at the front rail ends.
- **The two rows:** each says 3 screws, 1 more, reading 2.28× (left side) and 2.26× (right side).
- **Fix these:** one designer message, 13 s. Both rows read "fixed".
- **The fresh check reads 2.28 and 2.26,** as said. The case now holds at 2.15, by the plate, and Things to fix is empty.

**Fail first** (from a tree at 29dd891): every new behaviour failed. The DISAGREE edge pins passed there, by design:
they pin behaviour that didn't change.

**Mutants: 25, all caught.** Five survived the first round, each a gap in my tests (the code was right), and each now
has a test of its own: the screws laid where `marks.spots` lays them on a sheet's edge (the flows' moments never reached
them); a raked tie's thrust kept beside its frame load in the count; the hand row's own fix where no FEA reads it; what a hand-rule count reads where the FEA's side is lower there; a hand number with no demand to read it again by.
1. a joint row's count from the first case it speaks for, not the largest;
2. "1 more #8 screws";
3. a declared count laid from end to end, not 1½ in in;
4. exactly 1 in apart said to crowd;
5. a count with no "screws" in its fix let through;
6. `"screws": 0` taken as a count;
7. an apron end's screws laid as points;
8. a sheet edge's screws not laid again (survived, then caught);
9. a rake's thrust left out of the count (survived, then caught);
10. the FEA's and the hand's sides taken by the higher;
11. the hand rows' own fix dropped (survived, then caught);
12. a hung apron's screws counted with no "screws" in its fix;
13–15. `MIN_NODES` read as more than, `STATICS_TOL` as at or over, `DISAGREE` as more than;
16–18. `MIN_NODES` 5, `STATICS_TOL` 0.02, `DISAGREE` 0.2;
19. the declared count ignored by `marks.screws`;
20. a glued joint's uncounted screws counted in the fix-it;
21. the choice without its `JOINTS` entry;
22. the fix computed only where the FEA's side fails (survived, then caught: where the hand rule fails in shear and the
    FEA's side just passes in bearing, which screws don't move, the count read the hand's 2.37× where the fresh check
    reads the FEA's 2.2);
23. `beside`'s guard against a hand number with no demand dropped (survived, then caught; no row is built so, but it's
    pinned).

I had first argued 22 and 23 equivalent. 22 wasn't, so both were run.
24. the hung apron's capacity branch dropped (every hang waived): caught;
25. it taken at a pull capacity of 0 too (every hang standing): caught.
