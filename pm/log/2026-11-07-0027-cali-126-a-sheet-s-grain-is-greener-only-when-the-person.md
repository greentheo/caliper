### 2026-11-07 · CALI-126 (#150) · A sheet's grain is greener only when the person says it, and the maker is told
From #149's review (rule 6): a greener number may rest only on something the person said, and what they said must
reach the maker.
- **Assumed:** a `"grain"` the designer writes on a sheet in `construction()` is carried as `grain_assumed` and never
  reaches the verdict: the beam check takes the worse grain, and the card gives the advice ("Cut the top with its face
  grain running front to back and it's about 3.1 times over, not 1.6 times over: keep that under Will it hold? and it
  goes on the cut list.").
- **Stated:** the person's grain lives in the design (`design.grain`, `caliper.grain`), never the script: said in the
  chat ("cut the top with the grain front to back", deterministic, no Claude call; a direction is read against the
  span the last beam check measured) or by the Beam check's **Keep** button (`POST …/parts/{pid}/grain`). The next
  strength check gives it to `beam()`, where that grain's number, sag and by-thickness govern; until then the card
  says "You said: …. Check it holds again to use it."
- **The maker is told:** the cut plan on the page and the build book's cut lists say "Cut the top with its face grain
  running side to side (across the gap it spans)." (in the part's own directions once a check has measured the span:
  `span_axis` on a beam).
- **The Beam check line says which grain it used:** "with the grain along the span, as you said" or "the grain unknown:
  the weaker way", never a hard-coded "unknown"; the case's "by the plate check" says the same.
- No design of Theo's writes or states a grain (checked by hand, read-only), so nothing of his moves.
- **With #106:** the advice quotes a number only from a case whose own verdict is settled (it holds or fails): never
  one checked in the middle only, too coarse, on a filled-in shape or of an older version (`test_edge_foot`'s
  middle-only stool caught "about 4.2 times over" beside "checked in the middle only").
- Not here: an arrow on the pattern sheets (the line is on the cut list and in the book).
- **#151 review:**
  - **One phrase for the cut, everywhere** (`grain.phrase`), led by the part's own direction: "face grain running
    front to back, from one support to the other" (or "…, parallel to the supports"). It's the same in the Beam
    check's why, the card's advice, the Keep button and its reply, the chat, the cut list and the book; "along/across
    the gap" are gone (each read both ways). Pinned across all of them.
  - **The layout follows the grain, or says it doesn't:** `unfold_driver.mjs` finds each stated panel's grain on its
    flat (by its faces' OBJ group: one panel alone is "P1"), turns its outline so the grain runs along the sheet's
    length, nests turning end for end only, and puts the turn back into the placement. The bench's top went from
    900 × 300 on the sheet to 300 × 900 (its front-to-back grain along the 8 ft length). Per piece: follows, or
    why not ("it doesn't fit the sheet with its grain along the sheet's length", or its way isn't known before a
    check), on the page's cut plan, `cutlist.txt` and the book, beside the line.
  - **"cut the top with the grain"** with no way asks "which way: front to back, or side to side?"; a question about
    the grain ("should it run front to back?") is the chat's, never kept.
  - Pinned: advice from an unsettled case quotes no number; the book's line end to end (`release.make`); a sheet
    named in two parts asks which. Mutants (no settled filter, no book lines, no "say which one", no turn) each fail.
  - **Round 2 (blocking):** only cutting or laying a sheet is a grain to keep or ask about: a way ("front to back")
    or a cutting verb near "grain" ("cut the top with the grain", "its grain should run …"), and asked only when it
    names a sheet. "give the top a nice wood grain finish", "use a fine-grain plywood", "stain it to show the grain"
    go to the chat as ever. The nester turns a whole material end for end only, so the plan says what that cost ("…
    to keep the top's grain along the sheet: 3 sheets, against 2 turned freely", or that it took none). The Beam line
    says the cut's words once (in its why; then "with the grain as you said").
- Tests: tests/test_grain.py (14 with the review's: assumed never moves it, stated does, the part's own directions,
  refused grains and panels, the card's advice then "check again", unsettled advice, one phrase everywhere, the chat,
  no way asked, two parts, the page's line, the layout turned on a real cut plan, a layout that can't follow it, the
  book end to end). The mutant (the check taking the designer's grain) fails 3.
