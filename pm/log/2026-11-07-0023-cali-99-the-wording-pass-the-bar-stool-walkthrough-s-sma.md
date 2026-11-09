### 2026-11-07 · CALI-99 (#89) · The wording pass: the bar stool walkthrough's smaller findings and the reviews' nits
- **Named for what it is** (item 1): "I want to make a bar stool…" was "I want" (the stop words split at "to" before
  the request's lead came off). The lead comes off first, and it knows "Can you design…", "I'd like…", "Make me…".
- **A one-part design's top line is its part's description** (item 3), as *What do I buy?* reads it, not the raw
  sentence.
- **A print-time or weight objective offers the carve** (item 6) on a printed part with loads that isn't carved yet:
  "Carve the cone where it isn't working, to print less of it: try Carve it." (it goes to the carve's panel).
- **The reviews' nits:** the run picker says each run's own verdict (an older fail stays a fail, not "not trusted");
  the scorecard's trust text says "its shape couldn't be checked" when that's what it is; a fail on a filled-in shape
  is "likely weaker", and one whose shape couldn't be checked says that (`answers.filled_fail`); the heat callout's
  strength is rounded ("breaks near 13.6 MPa"); a plan with no key never says "press Build it".
- **#137's P2 list:** the least-safety box is never blank; a check that just ran resets *Test it* (it said "Check it
  holds first" right after one); the shop check is no ✓ over nothing worked out (a part whose plan couldn't be made
  leaves it waiting, said why: P2 item 10, rule 6), and its number says what it counts; the stray-face line's height
  in the design's units; an old reply's traceback is shown to its last line, with no server paths (`chat.shown`; the
  log keeps every word).
- Already done elsewhere: items 4 and 5 (the FEA's piece, "16 of its 16") in #139. Not here: item 2 (the questions
  read the shop, and offer to add an answer to it): a change to how the questions work, not wording; its own issue.
- Tests: tests/test_wording.py (20; 16 fail without this), and two suites' expectations for the new words.
- **#144 review: the offer asks what the Carve button asks.** On the bar stool, *How do I make it?* offered "Carve the
  cone skirt…" while the Carve button refused it. `load_study.blocked` is now the one test: it already fails
  (`already_fails`), its walls are too thin for any check (`too_thin`, #136), or its voxels don't connect
  (`unsupported`, carve only). It reads the default-voxel check (`default_check`: this version's coarsest, the voxels
  a carve runs at, not just the latest), with the words each button says. The design state gives each part its
  `blocked`; the page's `carveBlocked` and `lightenBlocked` read that and nothing else; `_carve_offer` makes no offer
  where it's set; the studies refuse on the same `already_fails`. On a copy of the stool (v7, 0.53, coarse): no offer,
  the button says "its check says it fails (0.5 times over, a coarse run…): make it hold first, then carve". Also
  pinned: one part's making plan raising leaves the shop check waiting, naming that part (not the one that worked);
  the stray-face line in the design's units through the card (`answers.answers`). Existing designs keep their names:
  `short_name` runs only when a design is made, so Theo's `I want` (its slug, part id and files) stays as it is.
  Tests: test_wording (+8), test_stray_faces (+1); the page tests take the server's `blocked`. Three mutants (offer
  ignores `blocked`, `settled = planned`, the stray line in mm) each fail them.
- **The gap, on Theo's own stool (no check of v7):** with no strength check of this version, `blocked` is
  `unchecked`. The Carve button is off ("Check it holds first: a carve starts from its strength check") and the card
  says "Check it holds first, then carve the cone skirt where it isn't working, to print less of it." (to *Will it
  hold?*), where it said "try Carve it" and the click was refused by the carve's own resolution check. Lightening isn't
  held for it (its holes are checked as it goes). The design card's strength goal reads as the part card does: "0.5
  times over" (`_times`), not "0.53x", and "last checked on v4: 1.7 times over, needs 2". Pinned with an older-run-only
  part and a part with no run; the mutant (no check = not blocked) fails 4.
