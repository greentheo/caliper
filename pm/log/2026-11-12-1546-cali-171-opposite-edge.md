### 2026-11-12 · CALI-171 (#266) · "And the opposite edge" is a strip and its mirror

The third part of #266. Theo asked for a fillet strip on "this edge and the opposite edge", and one part was made.

- **The person's own words go along.** An added part gets the message as asked, as well as the classifier's summary of
  it, which can drop "and the opposite edge".
- **"The opposite edge", "its mirror", "both edges / sides / corners"** with an edge picked: the designer is told to make
  the strip for the picked edge only, because the opposite one is made as its mirror.
- **The opposite edge is found, not guessed:**
  - the picked edge is flipped across its part's middle, on the axis where it sits furthest out;
  - the flip must land on an edge of that part, within 0.5 mm;
  - an edge in the middle on that axis is its own mirror and is skipped.
- **The second strip is a #246 mirror** of the first, across that plane (`<part>_opposite`). It's one script, and it
  follows the first. It's measured on the opposite edge as the first is on the pick.
- **What the reply says:**
  - Seated: "It sits on the edge you picked on stool, and its mirror fillet_strip_opposite sits on the opposite edge."
  - No opposite edge found: "! Built fillet_strip on the edge you picked, but I found no edge on stool opposite it, so
    there's one strip." That isn't a success, and nothing's mirrored.
  - The mirror measured off its edge: "✗ … but fillet_strip_opposite sits N mm off the opposite edge."

**Tests:** 6 more in `test_added_part_fits.py`, on a synthetic two-sided stool; 4 failed before. All 10 mutants are
caught. Two survived at first:
- the person's words when the summary drops them, now pinned;
- the mirror's own gap check. A mirror across a matched twin always lands within tolerance on real geometry, so its
  wiring is pinned with a measured miss stood in.

The around-files (chat, routes, first build, shared sizes, tipping, promote, build plan, pick scope, features, several
parts, mirrors) pass, 588.

**#269's rework merged forward** (a merge commit). The mirror is held to the same rule as the first strip: from outside
the part it's on ("✗ … but fillet_strip_opposite goes 3 mm into stool."), pinned and its mutant caught. An unusable pick
and a missing opposite edge both lead with "!". `test_added_part_fits` passes, 18.
After the merge, the added-part, chat, routes, mirrors, several-parts and pick-scope files pass, 294.

**Rework from the review (the foreman's four).**
1. **`_BOTH_EDGES` reads edge or corner wording only:** "this edge and the opposite edge", "both corners", "the other
   side's edge", "its twin". Words about the strip itself are one strip, pinned: "rounded on both sides", "I'll sand the
   other side smooth", "mirror the profile".
2. **The reply names which edge it mirrored to:**
   - by the host's piece where it has pieces ("the right side's inside corner": the piece the twin is on and the picked
     edge isn't);
   - else by its line ("the line from (280.95, 0, 300) to (280.95, 200, 300)");
   - a host with twins on two axes is asked about, not guessed: "! … it has an opposite edge across x, the line from …,
     and one across y, …: say which." Nothing's mirrored.
3. **Two edges asked for with one picked** ("this edge and this edge", "these two edges", "this edge and that one"):
   "! Built fillet_strip on the edge you picked, but I have one edge picked: pick the other one too, or say "the
   opposite edge"." Never one strip with a silent ✓.
4. **From #269:**
   - the depth into the picked part is measured without swallowing an error. One that can't be measured reads "!
     … I couldn't measure whether it goes into stool, so it isn't known to sit on it", and the round's result waits
     (deferred), never a pass;
   - "Every check on this part passes" is taken out under any "!" or "✗", wherever the line falls;
   - and from the review's notes: what a mirror breaks counts, since broke and fixed are worked out again with it in.

**Tests:** 13 more in `test_added_part_fits.py`; 11 failed before. All 9 mutants are caught. The added-part, chat, routes,
mirrors, several-parts, pick-scope and verdicts files pass, 346.
