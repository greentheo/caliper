### 2026-11-15 · CALI-186 (#297) · Preview a Lighten step's patterns and cut plan without cutting its holes in; reviewer-2's five asks on #306

Theo, 2026-11-14: "when I select a 'lighten', i selected 16 … it doesn't appear that I can then make the relevant cut plan".
- **The problem:** the patterns and the cut plan were of the part as it is. The only way to see a step's was to cut its holes in, which writes a version.
- **This PR:** the second of the foreman's two PRs (item 2), plus reviewer-2's five asks on #306, folded in as the foreman directed.

**What a preview is:**
- **One script for both:** `lighten.station_script(store, run, step)` is split out of `adopt`. It returns the script cutting the step in would write, with the same refusals:
  - an estimate;
  - an older version (`Stale`);
  - a run as the print;
  - a carved part;
  - holes outside a piece.

  `adopt` writes it, and a preview builds from it, so what's previewed is what gets cut.
- **Built in a scratch copy:** `previews.make` builds in a `mkdtemp` copy of the design.
  - **Left out of the copy:** versions/, previews/, patterns/, cutplans/, releases/, lighten/, and any study file over 1 MB, such as a load case's voxels. Step-stool-5's loads/ is 266 MB, and grain reads only a strength check's run.json.
  - **Untouched:** the design's versions, history, log, patterns and cut plans.
  - **Clean-up:** the copy is removed in a `finally`.
- **Named and stamped "preview":**
  - Every file is `preview-…`.
  - The patterns' page titles, projector SVGs and index say "PREVIEW, not the part yet: step N of lightening R".
  - The cut plan's files are renamed (its sheet folders and DXFs too), and its record names them as they are.
  - Its cut list starts with the stamp, and its own `preview.html` shows the sheets, the files and the cut list, and says not to send them to a machine.
- **Cached per (run, step, what):** at `previews/<run>-<NN>/<what>/`.
  - It's copied whole into place, then swapped in, so a failed build is never kept as made.
  - It's rebuilt when the step's script or design.yaml changed (a grain said since).
  - The newest 6 are kept.
- **Routes:**
  - `POST /api/designs/{slug}/lighten/{rid}/stations/{i}/preview {what}` runs as a part job (`meta=_on_part`, kind `preview`, and a delete waits for it: "being previewed"). It refuses up front what cutting it in would refuse.
  - `GET …/previews/{rid}/{i}/{what}/{path}` serves its files, refusing paths outside it.
- **Page:**
  - **Where:** the note each section already showed while a step is picked gets one button: "Preview step N's patterns" under Patterns, "Preview step N's cut plan" under Cut plan.
  - **When there's none:** for step 0, an estimate, or a run that isn't trusted.
  - **Once it's made:** an "Open step N's … ↗" link.

**reviewer-2's asks on #306:**
1. A greyed step button and the bar's `#adoptBtn` say why in a line beside them (`offWhy`), not only in a `title`.
2. The strength panel's "Other thicknesses" rows say "Ask for 1/2 in sheet (redesigns it; checked again after)". They wait while a Lighten step is picked (`pickedStep`, `askWait`), with the reason said once under the table. The Lighten table's estimates say theirs once the same way.
3. A case line beside its badge says "not checked" once: `caseWhy(c, run, false)` starts with the sentence. The station bar, which has no badge, keeps the word first.
4. Each load case carries `governing` from `load_study.governing_words` (in `design_state`), and `caseWhy` names it: "the top's plate check read 2.15x".
5. Pins: a failing coarse case keeps "the fail may be the model's", and an unresolved run's reason comes first, not only an unchecked one's.

**In the browser:** on :8016, with a scratch copy of step-stool-5 at v7 and Theo's v7 Lighten run, I picked step 10 (2.1x, holds):
- "Cut step 10's holes into step_stool (makes v8)" was live.
- All nine "Ask for" buttons (the strength panel's thicknesses and the estimate) were greyed, each table with "Step 10 is picked: …" said beneath it.
- **"Preview step 10's patterns"** gave a stamped index. It showed one wall cut in each side and 6 holes in the step: 41% of the walls and 6 holes, as step 10 says.
- **"Preview step 10's cut plan"** gave a stamped sheet with those holes, and every file was named `preview-`.
- **Afterwards:** the part was still v7, with no new patterns run, cut plan or history line, no `caliper-preview-*` left in the tempdir, and no server errors.
- **At 375 px,** nothing scrolls sideways.
- **The preview page's colours:** its heading was unreadable on the browser's dark background, so it now has a white body.
- **Not on screen:** the v7 check holds, so no unchecked case line showed. The v6 test covers that line.

**Tests:**
- **New:** `tests/test_step_previews.py`, 14 tests:
  - no version, and the step's holes shown;
  - every file named and stamped, every link a file;
  - page titles;
  - made once;
  - made again when design.yaml changed;
  - a failure leaves nothing;
  - the refusals;
  - adopt writes the previewed script;
  - pruning;
  - what the copy leaves out;
  - the cut plan (with unfold-to-sheets);
  - the route and its files;
  - the page's buttons and wiring.
- **The asks:** `tests/test_picked_step.py` gets 4 new tests (the bar's reason, the thicknesses, a failing coarse case, the server's `governing`), and its pins follow the new words.
- **Which was wrong, test or code:**
  - `test_part_menu`'s guard failed the first around run. It's right that every part job kind is registered, and `preview` wasn't (code). It's in `DOING`, and the guard's list has it.
  - Two of my new assertions were wrong (test): the page's `esc` doesn't escape `'`, and one check took in the estimate's own reason line.
  - The second around run (101 files) failed three older tests, and in all three the test was out of date (test): `test_coarse_steps`' page harness now loads `offWhy` and `askWait`; `test_lighten_sheet`'s two pins of the plate row's `sheetUse(…, pl.piece` call now end at the piece, with the words after it.
- **Mutants:** 39, all caught: 27 on the previews (the module, the stamp, the routes, the page) and 12 on the asks, including reviewer-2's two survivors. One ("any station picks") survived until the strength-case pick in the test was at a step other than 0.
- **Around runs:** first, 99 files (patterns, Lighten, cut plan, the API, the page, the guards); then 101 after the merge and the asks. Their failures are above, and the three files pass now.
- **One for #304:** the cut-plan preview test found a `caliper_sandbox_*` folder left in the tempdir after a real cut plan. That's the existing sandbox leak, not the preview's, so the test checks only `caliper-preview-*` folders.
