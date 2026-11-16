### 2026-11-16 · CALI-185 (#296) · #312 third round: an open conflict checks the more demanding; a Save settles only what was acted on; the guard as an ast walk

reviewer-2's re-check at 14f8207 left three must-fixes, all adopted by the foreman.

**1. The edge warning on Theo's step-stool-3.** Its forward tipping case sits at the front edge and counted as the edge's foot, so the reviewer's edits never warned. #314's fix lands here (see its own entry): `_edge_foot` reads strength cases only. The edge fixture keeps its tipping case at the edge now, and the reviewer's three edits warn with it there.

**2. The guard is an `ast` walk** (`_readers` in test_scenarios). It flags:
- every `["loads"]` or `.get("loads")`, either quote, on anything but a check's `ctx`, a part state's has-loads flag (`p`) or a run;
- an `.id == "loads_edge"` outside consistency.py;
- a `tipping.unchecked(` not fed `SC.declared` / `scenarios.declared`.

A line may still say which loads it means (`# script's loads:` / `# edited:`). Only `prepare` is exempt in load_study, and scenarios.py is the edited loads' own module.
- Reviewer-2's ten readers are pinned: each is caught, including the eight the line pattern let through. Five that should pass are pinned too: a check's `ctx`, a has-loads flag, `prepare`, a marked line, and `tipping.unchecked(SC.declared(…))`.
- Today's source is clean under it.

**3. An open conflict** (the design changed or dropped a case under an edit) **checks the more demanding until the person chooses, and says which:**
- **The two order** (the same name, way and box): the larger, by amount × margin. "checked at the design's 300 lb until you choose; yours is 260 lb", or "checked at yours, 260 lb, until you choose; the design's is 200 lb".
- **They don't order:** both, each under its own name ("… (yours)", "… (the design's)"): "both checked until you choose".
- **Theirs turned off:** the design's.
- **A dropped case:** theirs, "still checked until you choose".

A choice is a choice:
- A Save settles only the conflict rows acted on: **Take the design's**, or **Keep mine** (new, beside it). Every other open one keeps its old base and stays open, edited or not.
- **Keep mine** on a dropped case keeps it as a row they added.
- The Save's message and its history line say what's still open.

Said everywhere:
- `scenarios.asked` gives the open questions in words.
- `drift` says them every time, not only after the design changes.
- The scorecard's strength note says "an open question about its loads: …", trust "not resolved".
- The release book says it under Will it hold?, and its record keeps `loads_asked`.

**Small asks:**
- The card's line ends on its question, never "?.".
- Taking the design's for the only edit, with the supports the script's, leaves no override (`overridden: false`).
- A Save names what it kept open.

**Tests:**
- 11 new or changed tests failed first on 14f8207 plus the #314 change. The guard tests passed from the start: the scanner is in the test itself.
- One old test was wrong for the new rule: the rating conflict's expected sentence lacked the "checked at…" words.
- **Mutants: 20 of 20 caught.** Four survived the first pass, and each was the test's gap, now closed:
  - **a row of theirs turned off:** pinned with the design's value falling, where checking "theirs" would check nothing;
  - **the questions said only after a design change:** pinned by drift still asking after a Save that kept two open;
  - **the scorecard's trust:** the coarse test run was already "not resolved" for its walls. It's now pinned with `unresolved` patched off, against the same run with no question;
  - **Keep mine's wiring on the page:** pinned by its line, as Take the design's is.
