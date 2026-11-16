### 2026-11-16 · CALI-185 (#296) · #312 re-check: every reader of a part's loads reads what its check reads; the override is edits on the script

reviewer-2's re-check of #312 found two more must-fixes. Both are fixed here.

**1. Some readers still read the script's loads.**

- `consistency.bare_edge` read the script's `loads()`, so did the card's edge line. So did the seat's "Not checked yet" list (`tipping.unchecked`).
- The reviewer's step-stool edits (front edge removed, turned off, or moved to the middle) left the script's front-edge case standing, so nothing warned, and a ✓ counted as one.
- New `scenarios.declared(store, pid)`: the part's declarations with the loads its check reads (the edited scenarios that are on, and the supports), beside the script's tipping cases, which no scenario edits. It's the script's own where nothing's edited.
- `bare_edge` asks `_edge_foot` of those. The card's edge line now reads `bare_edge`, not the script-only `loads_edge` row. The seat list reads `scenarios.declared`.
- A guard test: outside scenarios.py and load_study, any line that reads `loads` off a part's declarations has to say which loads it means. The deliberate ones are marked `# script's loads:`:
  - `loads_land` (the script's own loads must land);
  - the tipping cases;
  - the drawing in pictures;
  - "has it any loads at all".

  No one outside consistency.py may read the `loads_edge` row, and `tipping.unchecked(C.declared` is refused.

**2. The override replaced the script's loads; now it's per-row edits on the script.**

- Stored: `{"edits": [{"of": the script case, or None for one added, "row", "base": the script case when edited}], "supports", "script_sha", "seen"}`.
- A row saved unchanged isn't stored; it stays the script's, entirely, as the script changes. A script row left out of a save becomes an "off" edit.
- Read (`_effective`):
  - every script case as the script has it now, unless edited;
  - an edit's box follows its script case's box until moved;
  - an edit whose case the design changed (numbers or name; not the box) or dropped is still read, with `conflict`;
  - added rows follow.
- `drift` (said in the reply and on the card) now also says:
  - "you'd edited 'X' to 100 kg; the design now asks 200 kg: keep yours, or take the design's?";
  - "you'd edited 'X'; the design no longer has it";
  - "the design added 'Y': it's checked";
  - "yours kept: …".
- The editor marks each row as yours or its script's. A conflict row gets **Take the design's**; saving keeps yours, and either way the conflict is settled.
- An override saved before this change (whole rows) reads as edits of its namesakes.
- Small asks:
  - a standard's case only moved is "EN 14183, moved: 150 kg, …", not "edited";
  - a restore's history line says what it did to the loads (`scenarios.restored`, shared with the chat reply).

**Pinned:**

- the reviewer's edge edits, on the stool without rails (step held on two sides only): removed, turned off, moved to the middle. "Removed with the rating off" can't be pinned on a two-case fixture: nothing is left on, which is refused.
- a seat's front-edge case removed: said;
- the reviewer's refine: 300 lb standing on the renamed front edge, a new kneeling case, the rating kept at 100 kg and said;
- a rating changed under the edit: asked, then taken;
- a dropped case;
- GET after a refine shows the followed box, and an untouched save leaves the rows unmoved.

11 of the 12 new tests failed on c868615. The one that passed (the followed box) was already fixed in the first round and is pinned here.

**Fault calls:**

- The code was wrong for both must-fixes.
- The test was wrong twice:
  - my first fixture kept the stool's rails, so its step was held on four sides and never two-sided;
  - it kept a tipping case at the front edge, which `_edge_foot` counts as a foot there.

**Found, not changed:** `_edge_foot` counts a tipping case standing at the free edge as the edge's foot. A tipping case checks that it won't tip, not that it holds, so a script whose only edge case is a tipping case gets no warning. That's the same reasoning `tipping.unchecked` already follows. Raised for the foreman; it's outside this PR.
