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
