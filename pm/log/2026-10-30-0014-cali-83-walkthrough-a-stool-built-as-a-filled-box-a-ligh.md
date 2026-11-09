### 2026-10-30 · CALI-83 (#55) · Walkthrough: a stool built as a filled box; a lightening preview read as the part
- **Theo's walkthrough** ("let's walk through it… see if I can recreate it in the tool without you having to write
  all kinds of scripts"), with first run, the four questions and his own words. Two things he flagged:
  "the box is filled in instead of hollow" and "the cut plan doesn't have the holes or side cutouts removed".
- **Filled in:** the designer's `build()` made a solid 24 × 12 × 6 in block while `construction()` listed six
  panels. Every panel lay in the block and covered its surface, so the checks passed it, and the strength check and
  the lightening study ran on a block. For a part with `loads()`, the solid must now be its pieces (0.67–1.25× their
  volume): the designer is told "build() is filled in", and a part already built that way says so on *What is it?*.
  The camper's lofted cargo box is 8.9× its pieces but has no `loads()` (it's kept for drag; weighed from its
  pieces), so it's left alone; the sample stool and Theo's first stool are exactly 1.0.
- **No holes on the cut plan:** the server log showed lightening step 17 previewed five times and never cut in. The
  bar now says **Preview, not cut yet**, and while one is shown the patterns and cut plan say they're of the part as
  it is.
- Also from the walkthrough, filed and done on their own branch: printed parts (#53), and a plywood top on printed
  sides, carved (#54).
- Commit: `292d887`, PR #56.
