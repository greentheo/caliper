# Caliper work log

Append-only. Newest first. One entry per shipped task or notable decision.
Format: `### YYYY-MM-DD · CALI-N · title` then what changed, tests, and the commit hash.

### 2026-11-07 · CALI-116 (#118) · Plywood's beam width takes its orthotropy, the safe side
- **`load_study.beam()`** scales the effective width under a foot by `orthotropic(mat)` = (D_across / D_along)^¼ (the
  material's `E_across` if given, else its strength ratio across; 0.841 for ply) when the face grain runs along the
  span, the edge's share too, never past the panel's width (BS 8110 cl. 3.5.2.2(b)). `width_along_mm` and
  `orthotropic` are on the record. The grain's way unknown, `safety_across` (the verdict) is the worse of the two.
- **The `why` says so,** and the page's Load panel shows a two-sided top as a **Beam check** with its `why`, not "held all
  round, edges free to turn" (design.js v=53).
- **Before → after** (the plate numbers; the FEA and every verdict unchanged, since the verdict already took the grain
  across the gap at half strength):

  | fixture · case | width (mm) | grain along the span | verdict |
  |---|---|---|---|
  | test stool · front edge | 206.7 → 173.8 | 2.37 → 1.99 | 1.19 ✗ → 1.19 ✗ |
  | test stool · middle | 254.0 → 238.5 | 2.91 → 2.74 | 1.46 ✗ → 1.46 ✗ |
  | MIXED · front edge | 190.0 → 159.8 | 1.15 → 0.97 | 0.57 ✗ → 0.57 ✗ |
  | MIXED · middle | 220.0 → 210.2 | 1.33 → 1.27 | 0.66 ✗ → 0.66 ✗ |

  The greener number was the advice: "cut with its face grain running across the gap and it's about 2.4 times over"
  for the test stool's front edge is now 2.0.
- **NEEDS ENGINEER CHECK:** the factor (#42: or b_ef = M_beam / m_plate, or let the plate check govern).
- `tests/test_orthotropic.py` (7; six fail on main).
- **Merged forward onto main's one verdict (#132):** the plate or beam check gets its own verdict on the server
  (`verdicts.meets` of its worse-grain number against the run's need, only where the case is settled: never green on
  a not-trusted, unresolved or older case), and the Beam check panel takes its colour and word from it. Before, the
  panel's number was plain bold. No number moves. Both guards pass.
- **#122 review:** pinned that no plate or beam number reads green on a case that isn't settled (too coarse, or an
  older version): it reads as its case does, and dropping the guard fails the test. Merged main (#139): the panel's
  plate line is one expression with the beam, the ring and the rectangle, each with its number in its verdict's colour
  (`plNum`). The sag beside "grain unknown" is the worse grain's (`beam`'s `sag_worse`: along the span its own E on
  the narrower width, across it its stiffness across on the whole width): for ply, half as stiff across, so twice
  the isotropic sag where that governs. `test_beam_width`'s sag reads the same.
### 2026-11-07 · CALI-122 (#137) · The bar stool's pre-flight: its broken rule said, where it fails, no carve on a fail
From the reviewer's pre-flight of Theo's bar stool v7 (a copy; nothing of Theo's touched), with the foreman's
correction: the run's "seat top" was a mislabel.
1. **A part's own rules, measured, with their verdicts** (`part_rules.measured`: once per version, in memory, nothing
   written). The page's *Rules on this part* shows each rule's verdict, and what it measured where it doesn't hold;
   *Design checks* falls back to the parts' rules. A rule it breaks leads *Will it work?*, on the part and the design:
   "✗ Breaks its rule shell_wall_thickness: its walls are 0.25 mm around z 16.1 in; it says at least 2.85 mm."
2. **Where it fails, and how sure.** The FEA's hottest voxel was named after the nearest *wood* piece even in the
   printed part: v7's "seat top" was at z 389 mm, in the cone's 0.25 mm webs (the foreman's v1 run too). `in` now
   names a piece only within a voxel of it, else the printed part, and the run records the wall there (`wall_mm`,
   measured within two voxels; a piece's own thickness). The line says where the worst stress is, in one run at its
   voxel size; the coarse caveat only where the walls there are too thin to see, otherwise the thin walls are said
   apart. An older run (no `wall_mm`) keeps the old words, and its label is never shown: the page's "works hardest
   in seat top" (Theo's v4 card on main) and a trial's "where" name a piece only from a run that recorded its wall
   (`peak_in`; the page says "around 27.8 in up" instead). One wall number, with where.
3. **No Carve, no Lighten, on a part that already fails as drawn** (`load_study.already_fails`, from this version's
   own check's one verdict): "Can't carve it: it already fails (0.5 times over, in …): make it hold first, then
   carve." The page's Carve and Lighten are off and say the same (`carveBlocked`, `lightenBlocked`).
4. **A carve says how long it has run** ("· running for 6 min"), repainted every 30 s: its sweep reports little before
   step 1. "the printed PETG (printed)" (P2 item 8) reads "the printed PETG".
5. **A goal says its limit:** "✗ Mesh cone keeps total weight down (assumed): 13.1 lb, over its 10 lb cap" on the
   card (`_against`), and "(cap 10 lb)" in the Score panel.
7. **A disc on a ring gets its own plate check** (Roark Table 11.2 case 16, `ring_plate`; the ring is the widest one
   the part beneath holds 90% of the way round, probed just under the panel). The bar stool's seat: ring 270 mm,
   4 in pad, 3/4 in ply: 4.57 MPa, 3.3x across the grain; the foreman's hand check gave about 4.5 MPa. A failing line gives it as a second opinion
   ("By hand, the seat top on its own, as a round plate on its 10.6 in ring: …"). The pad is measured in the panel's
   plane (the disc's frame ran diagonal, and read the 4 in pad as 119.5 mm). Never "only 16 of its 16 edges rest".
   NEEDS ENGINEER CHECK: the round-plate formula and the ring as its support.
- **The pre-flight again, on a fresh copy of the stool** (its strength check re-run, no live calls): "✗ Breaks its rule
  shell_wall_thickness: its walls are 0.25 mm around z 16.1 in; it says at least 2.85 mm." / "Doesn't hold 250 lb
  person seated: only about 0.5 times over, and it needs 2. Its worst stress, in one run at 3/16 in voxels, is in the
  cone skirt around z 15.3 in, among 7/32 in walls the voxels can't see: the fail may be the model's. … By hand, the
  seat top on its own, as a round plate on its 10.6 in ring: 3.3 times over." / "✗ … 13.1 lb, over its 10 lb cap."
  Carve and Lighten refused. Theo's own folder has no v7 strength run (its newest is v4): these read after he checks
  v7 again.
- The reviewer's nit on #132: a carved step that doesn't close up is an amber dot (#136 draws dots by verdict), pinned.
- Not here: P2 items 6, 9–12 (#89's wording pass), and a live first run (no key).
- **#139 review, the blocker:** `goalLimit` called `scoreView`'s own `num`, so a goal with a number threw "num is not
  defined" and blanked the inspector (a global stub in the test hid it). It's `scoreNum`, at module level, tested
  unstubbed with `scoreView` itself. A refused job reads without its exception's name: `follow()` passes the job's
  error through `plainly()` (main said "⚠ ValueError: Can't carve it…" since #136). *Show the stress* names the peak
  by `peakWhere`, never an old run's "seat top".
- **#139 review, items 4–7:** each wall number says which wall ("its thinnest walls, 0.25 mm around z 16.1 in"; "the
  worst stress is in the cone skirt around z 15.3 in, where its wall is 5.2 mm"), and walls and voxels are in mm
  everywhere, heights and positions in the design's units (`_wall`; the chat's small lengths keep their fractions,
  `_small_len`). The seat's ring is probed 1 mm under it in 1 mm steps and said as its outer edge ("held at its ring's
  outer edge (10.6 in across)": the cone flares to r 135 mm there). An older run's stored "only 16 of its 16 edges"
  is rebuilt from its numbers (`load_study.plate_why`). A refusal on a coarse run hedges as the strength line does:
  "its check says it fails (0.5 times over, a coarse run: the fail may be the model's; …): make it hold first".
- Tests: tests/test_preflight_bar_stool.py (17), and touched suites' expectations for the new words. Stacked on #136
  (its too-thin words), on #132's one verdict.

### 2026-11-07 · CALI-121 (#134 follow-up) · The carve-through-the-API test waits 1,500 s for its job, not 900
- `test_mixed::test_carving_through_the_api` waits for its carve job before it reads the run. On a loaded machine the
  job took 790 s on its own and over 900 s twice beside two other test runs (#134's merge-forward), so the test timed
  out with the job still running. A CI runner varies as much: the wait is 1,500 s, which a carve that hangs still
  fails. No code changed.

### 2026-11-07 · CALI-106 (#136 review, round 2) · What a refused carve asks for, said apart; the page keeps it off
- **The line asks two things apart** (thickening to the rule's 2.85 mm doesn't unblock a carve): printing and the
  part's own rule, "too thin for a 0.4 mm nozzle to print and for your rule shell_wall_thickness (at least 2.85 mm):
  thicken them to that"; and the strength check, in mm, "For a strength carve, walls must be at least 9.2 mm at this
  size, so check it by hand or with a test piece instead". With no rule and nothing printed, only the second.
- **The page keeps a blocked Carve off** after a job ends (`paintCarve` set `disabled` from the job alone, so a cancel
  re-enabled "Carve it again"), and a refusal reads without its exception's name (`plainly`: no "ValueError: …").
- **Lighten on a coarse run** says "Not resolved yet: the check was too coarse to see its walls…" (or "Not checked"),
  from the steps' `lighten_step` verdicts, as Studies does; it said "Nothing lighter still holds", a false ✗.
- Pins for the review's survivors: a coarse fail stays a fail (`carve_step`, `lighten_step`), and Lighten's `disabled`.
- Tests: tests/test_coarse_steps.py (16; 4 of the new fail without this, the fifth pins a fail). The review's last two
  pins: a coarse fail stays a fail with the whole part holding (`whole_holds: True`, where the whole-holds branch can't
  mask it), and the page's own refusal goes through `plainly()` (raw `e.message` fails it).

### 2026-11-07 · CALI-106 (#101, #136 review) · A refused carve says where the thin walls are and what to change
- **Where:** `measure.thinnest_wall` returns the thinnest wall and where it is (the middle of its ray);
  `min_wall_thickness` is its number. `load_study._thin` says which it is: a piece by name, or a measured wall's
  place. The strength record carries `thinnest_where`.
- **What to change:** `load_study.thin_words`, in the design's units: the wall, where, the size the strength check
  sees walls from at this size, a 0.4 mm nozzle where it's printed and thinner, and the part's own `min_wall >= …`
  rule (`wall_rule`, its spec's or the design's, read with `safe_eval`); otherwise "Thicken them first."
  `resolution()` carries it (`said`, `where`), the carve refuses with "Can't carve it by strength: …", and a too-thin
  check stores it as `thin_said`, which the page's disabled Carve and Lighten say.
- **One wall number** (#137 item 2, the same words): under 1 mm, two places, in `answers._wall` and the page's
  `wallLen`. The bar stool's 0.25 mm wall read 0.2 mm on the card and 0.3 mm on the page.
- On a copy of Theo's bar stool v7: "its 0.25 mm walls around z 16.1 in … Your rule shell_wall_thickness says at
  least 2.85 mm: thicken them to that first." z 409 mm, r ≈ 169 mm: the webs between the openings, where the
  foreman found them.
- Tests: tests/test_coarse_steps.py (+5: where, the line on the spool and on the stool's numbers, the refused carve,
  one wall number on both sides, the page's blocked carve). Touched suites: 187 passed locally; CI is the full run.

### 2026-11-07 · CALI-106 (#101) · A carve or lightening step on voxels too coarse to see the wall is no "holds"
- **Carve and lighten record whether their voxels see the walls** (`load_study.resolution`, from the same set-up the
  strength check uses): `thinnest_mm`, `across`, `resolved`, and unresolved, `finer` or `too_thin`.
- **A step that holds on a run that doesn't see its walls is "not resolved"** (or "not checked" where no run a study
  may make could see them), through `verdicts.station`/`carve_step`/`lighten_step` (stacked on #132's one verdict);
  a fail stays a fail, not trusted still ranks above it. Every reader: the chart's dots (amber), "the lightest step
  where the printed part holds" line, the station bar and its **Carve it like this** / **Cut these holes** (off, with
  why), the Studies rows, the carve's chat reply and its closing message.
- **Where no run can see the walls it isn't carved:** `carve.study` stops before carving, "Its walls are too thin for
  the voxel check at this size, so it can't be carved by strength", and the page's Carve and Lighten buttons are off
  with that line. Also off, with its reason, where the default check's voxels don't connect (#102's note). Theo's
  bar stool v7 (a copy): a 0.25 mm wall at 4.6 mm voxels, too thin, so Carve isn't offered.
- `tests/test_coarse_steps.py`: the thin printed tube carved at one voxel through reads not resolved at every step that
  holds (and in the page's state, Studies and the chat), at four it reads as its safety says; `resolution` on the bar
  stool's numbers; a too-thin part isn't carved; lightening's coarse steps; the page's buttons.


### 2026-11-07 · CALI-112 (#114) · One verdict function every reader asks
- **`verdicts.py`:** kinds worst first (`fails`, `untrusted`, `unchecked`, `unresolved`, `edge`, `stale`,
  `waiting`, `holds`), each with a status, a word and `counts_as_pass`; `case`, `run`, `goal`, `meets`, `station`,
  `check`, `summary`, `of`. A new kind is one entry. Precedence as the PRs settled it: a ✗ stays a ✗, then not
  trusted, not resolved, middle only, older version, waiting.
- **Every reader asks it** (the audit is in the PR): the part and design cards, the make card, the scorecard's
  statuses, the book's header, its Will it hold? row and its marks, the kids' book, Studies, the chat's facts, the
  picture reply and the chat's ok for it, the history line, the study's closing message, and the page's badges,
  run word, history line and stress bar (from `design_state`'s `verdict` on every run, case and history line).
  Producers and searches carry `# producer` / `# search`.
- **What the audit found, now fixed:** a fail on a filled-in block read "not trusted" on the scorecard (✗ on the card);
  the kids' book said "It should hold …, 1.2 times over" for a stool that fails; the history read "holds" for a check
  on a filled-in block; "✓ I cut a T. rex" led a ✗; Studies showed a card with checks still unknown green; a design
  with no checks read "Ready to cut — 0 of 0".
- `tests/test_verdicts.py` (37; can't import on main): two grep guards (Python and the page), every kind through
  every reader (cards, book row, kids' book, Studies, picture reply, page badges in node), the precedence, the summary,
  `goal`. Tests that read the old fields read the verdict now. design.js v=67.
- **#132 review (the foreman's sweep), A–D:** a design's verdict never leaves a part out (a part unchecked, older or
  errored is that: `measured()`, the scorecard, the kids' book, frame runs now record their version); `stale` is
  produced wherever a run isn't the part's version (badges, the part card, the chat's facts, the make card, Studies
  rows, releases via `verdicts.release`); carve steps (`carve_step`: the whole part and filled-in too), lightening
  steps (`lighten_step`: an estimate is its own kind), the plate check's rows, the first reply (worst first), a part's
  rules (`_rules_line`), trials (held but short), `promote`'s `holds_now` (unknown by default, `verdicts.rule`) and
  app.js's badge all ask the verdict; goals compare in `verdicts.compare`. Both guards widened (`< min_safety`,
  `>= limit`/`lim`, `ready`, `best`, `holds_now`; every `.holds`, `whole_holds`, `safety_across >=` in design.js and
  app.js): on the pre-rework head both fail, with all 13 of `tests/test_verdicts_sweep.py`.
- **#132 review, round 2:** the release panel reads `verdicts.release` (ready as made and for the parts as they are,
  its own reason when not); a revision's history stores its report's verdict (`verdicts.report`): a fail only with a
  failure, pass plus a waiting check is "not all checked", only waiting or nothing is "nothing checked yet", never
  red; older records read through `verdicts.history`. `summary(None)` and `meets(…, None)` wait; `release()` keeps
  its own reason; `to_text` and the CLI say ALL PASS only with nothing waiting; lighten's two searches marked as such.
  Both guards cover `ready` and `all_pass` now.
- **Merged with main's #124:** a carved step marked `closed: False` (its part doesn't close up) is never a pass:
  `verdicts.station` reads it "not checked", with its why, so `carve_step`, the step offered (`_offer`, and the
  lightest on a cancel), the chart dot and **Use this step** (off) all say so from the one verdict.

### 2026-11-07 · CALI-119 (#127) · A rule over the plan's own numbers is decided when it's planned; no rule sinks the plan
- **#117's live re-run:** the camper's planner wrote `tube_size * 25.4 <= 50.8` (the frame tube fits the 2 in
  receiver) twice; #117 refused a numbers-only rule, so the plan fell back to one part.
- **Decided at plan time** (`plan._by_the_numbers`): true, it's a note ("the frame tube fits the receiver (by the
  numbers: tube_size <= receiver)"), not a check; false, the plan contradicts itself and is refused with it, the
  numbers named ("tube_size * 25.4 <= 50.8 is false (tube_size 50.8 mm); lengths in a check read in mm", so the
  retry can see the slip); literals alone are left out, said.
- **No rule sinks the plan:** after the one retry a rule that still fails (an `=`, an unknown part, a contradiction)
  is left out with why ("I left out the check '…' (…): …" in the review, on the card); only a plan-level fault (no
  parts, a cycle, no answer) falls back to one part.
- **Units in `classify`:** speeds (mph, km/h, m/s) and masses (lb, kg) compare with what the person said, so "60 mph"
  is the planner's 26.82 m/s (or the "m" it wrote for a speed); skeleton units take m/s, km/h and mph.
- `tests/test_plan_numbers.py` (15; 14 fail on main), the camper's rule verbatim; #117's tests updated (a numbers-only
  rule is a note, a contradiction or left out; refused twice, the plan stands). design.js v=64.
- **#130 review:** deciding a rule uses the checks' own `approx` and `within`, and any error while deciding is that
  rule's fault (`PlanError(rule=…)`: retried, then left out and said), never the plan's. **A decided rule is plan
  data:** it stays in `rules` (never a check: `binding()` and the card's checks leave it out), its note is worked out
  on every validate, and what's left out is the plan's `left_out` field, so a revision shows both to the planner and
  "make the frame tube 3 in" is refused with "the frame tube fits the receiver, but tube_size <= receiver is false
  (tube_size 76.2 mm, …)", the plan as it was (a revision never drops a rule). A speed goes by its unit, never its
  name ("m" is a length). The card says "by the numbers" and a check's name once. Tests pin a note's whole path
  (the reply, the saved plan, the card, Keep) and the refused edit.
  Then: `left_out` is validate's own (a planner's answer can't claim a check was left out) plus, through an edit,
  the prior plan's; the "lengths in a check read in mm" hint goes to the planner's retry (`PlanError.hint`), never
  into what the person reads; both pinned.

### 2026-11-07 · CALI-117 (#105) · A carved step whose part doesn't close up is never offered or adopted
- **What it was:** with #106's front-edge foot, and on main's own carve-down test once BLAS ran on one thread (#121's
  CI), the carve picked a step whose adopted part wasn't watertight. Which voxels a run carves follows the summation
  order, so it came and went; a fresh run here was watertight at every stage (station, wood, join, STL reload).
  A part that isn't watertight can't be voxelized, so the check adopting it runs fails or reads wrong.
- **Now:** each step's mesh is repaired if a fill closes it (`carve._closed`: merge, drop degenerate faces, fill holes,
  fix normals) and otherwise marked `closed: False` with why. The step offered is the lightest that holds **and**
  whose part, as adopting it builds it (`carve._adopted`: the wood as drawn joined to the carved print), closes up;
  one that doesn't is marked and the next is tried. `adopt` refuses a step that doesn't close (`carve.NotClosed`, a
  422 with the reason) and checks the STL as it will be read back; nothing is written for it. The panel shows "Can't
  use this step: …" and its Carve button is off. design.js v=56.
- `tests/test_carve_closed.py`: a small hole filled and a big one not; every carved step forced to leak (not offered,
  adopt refused, nothing written); a join with the wood forced to leak (a small gap repaired and adopted watertight,
  a big one refused) and the study not offering it.
- **#124 review, the cause:** a **pinch**. Where two surfaces of the carved part meet along an edge, the adopted
  shape keeps two vertices at one point apart by index: watertight in memory, and once merged (any STL round trip)
  four faces share an edge and it isn't (#105's 6,011 vertices, 12,060 faces). `_closed` judged the in-memory form,
  so the study offered step 2 and `adopt` refused it. Now `_closed` judges a merged copy, as it reads back, so offer
  and adopt agree; a pinch isn't something a fill mends, so that step is marked. `_offer` builds the script once.
  Tests: a pinch along an edge (closed in memory, refused merged; one meeting only at a corner reads back closed),
  and #105's repro (MIXED with its edge foot, 40 lb, 4 steps to 0.6): the step offered adopts, watertight
  (`slow`: several minutes).

### 2026-11-07 · CALI-120 (#128) · The server keys the page's scripts and styles; no PR bumps ?v= again
- **`server.keyed_page`** serves `/`, `/index.html` and `/classic` with every `?v=` on the page's own `.js` and
  `.css` set to a 10-character hash of that file (`cache_key`), read per request: a changed `design.js` is a new key on
  reload, an unchanged one the same. The page itself is `no-store`. The pages keep `?v=dev` and never change for it
  again. The vendored three.js is imported by version-pinned path through the importmap, so it needs no key.
- **Why:** each merge to `main` made every other open PR conflict on `design.js?v=N` (tonight #122, #124 and #125
  each merged `main` again only for it, a full CI run each).
- CONTRIBUTING.md and firm/NIGHT_SHIFT.md: no bump step; the server does it.
- `tests/test_cache_key.py` (3): the key follows the file and only the file; the served pages are keyed and
  `no-store`; the pages keep the placeholder.

### 2026-11-07 · CALI-114 (#116) · CI runs the suite across the runner's cores
- **`pytest-xdist`** is in the requirements. CI runs `pytest -n auto --durations=25 -m "not serial"` with
  `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `OPENBLAS_NUM_THREADS` at 1, so four FEA workers don't fight over four
  cores. A second step runs anything marked `serial` on its own (exit 5, "no tests", passes once none is).
- **Locally `pytest -rs` stays the default,** and `-n auto` is optional (TESTING.md).
- **Before,** on main: the test step took 51.5 min (646a20a) and 40.8 min (ad2f296). After: in the PR, from its CI
  runs, with `--durations=25`'s slowest tests.
- **The carve-down test is marked `serial`** (7cdc550): in parallel, with one BLAS thread, it adopted a step that
  wasn't watertight (#105, fixed by #124). After #124 merges, the mark comes off.

### 2026-11-07 · CALI-118 (#126) · A stray face from the CAD's meshing isn't the part; an open part is said, never thrown
- **The cause:** OCCT's mesher fans a cone face's triangles from its apex, and one comes out with two corners on the
  apex: a sliver of no area along the cone's seam. Any cone that runs to its apex does it
  (`cq.Solid.makeCone(30, 0, 40)`). On Theo's bar stool v7 (a copy) it was face 128, the cone, at its apex on the
  flange (z 14–15.6 mm): 22,772 faces closed and this one apart, so every boolean threw "Not all meshes are volumes!".
- **`measure.clean`**, where every built part becomes a mesh: faces with no area go, and so does a loose open shell
  under `STRAY_SHARE` (1e-6) of the part's surface beside a closed body (it bounds nothing: at the 0.05 mm
  tolerance it moves the volume by about 0.1 mm³ on the bar stool). Said once, `mesh.metadata["strays"]`, and on the
  part card: "I left out 1 stray face from the CAD's meshing (at z 14.0–15.6 mm): it enclosed nothing and weighs
  nothing." A bigger open shell, or a real opening, is kept.
- **An open part is said, never thrown:** `measure.open_near` says where ("near z 40 mm"); `printed_solid` refuses
  a boolean on it, so (on #125's fail-soft) its weight is "not checked: its shape isn't closed near z 40 mm"; the
  strength check (and carve, lighten and the picture, which share `prepare`) says "not checked: its shape isn't
  closed near …, so it can't be voxelized".
- **The bar stool v7 copy:** closed, weighed at 13.1 lb printed included (v7 is a bigger part than v6's 10.9 lb: a
  1 in fillet for ½ in, a new opening pattern; 10.4 L of solid against 7.7 L), scored and released (below).
- `part_scripts.md`: a cone that stops short of its point has no sliver to leave out.
- `tests/test_stray_faces.py` (9; they can't import on main): three real CAD cones, a closed mesh and one stray
  triangle (dropped, said, its weight unchanged), a real opening and a big open shell (kept, said where), a cone
  part weighed whole with the card's line, and an open part (not checked, said, `/balance` 200, the page 200).
  Built on #125 (its fail-soft weighing). Closed is judged as it reads back (merged; #124's
  review). design.js v=65.

### 2026-11-07 · CALI-111 (#112) · An all-printed design gets a build package, and the book weighs what the card does
- **`cutplan.run`** makes its run folder whatever the materials. An all-printed part's cut list says "Nothing to cut:
  it's all printed." (The release raised FileNotFoundError on the tube.)
- **The 1.6 lb vs 10.9 lb:** the same card on the bar stool's copy said `weight.i_want` 10.9 lb and `weight.total_lb`
  1.6 lb. `construction.balance()` left out every printed piece; `report()` weighs them (`with_printed`). So the
  book's ✓ was wrong and the design card's ✗ 10.9 lb right. `balance()` now weighs printed pieces too.
- **A card from the old scorer is out of date:** cards carry `scorer: 2`. `list_cards` marks an older one `outdated`,
  the release scores again rather than reuse it, and the page and design card say "score it again". The camper
  sample's shipped card is re-scored (its verdicts the same; waste $90.30 → $90.24 from older drift).
- `tests/test_printed_release.py` (4; all fail on main): the tube's package, the total against each part's weight, the
  book's numbers equal to the live card's for the same version (a weight goal it fails is ✗ in both), and an old card
  re-scored. design.js v=61.
- **#125 review:** a printed piece whose solid can't be made (the bar stool v7's throw, #126) fails soft: `with_printed`
  marks it unweighed, and that part's weight, the total and the hitch's are **unknown**, never the rest's; the weight
  check reads "not checked: the printed part's shape isn't closed (…)", the design card and the page say so, and
  `/balance` answers 200 with the note. No `was`/change against a card from an older scorer ("scored differently
  since"). `compute` says to bump `SCORER` when a metric's meaning changes.

### 2026-11-07 · CALI-115 (#117) · The planner's live-run findings, before #3b builds on plans
- **Fixed only for what you have:** a `fixed` part whose words say it's made (welded, printed, cut, plasma-cut, to
  build…) is refused with that reason, and so is any fixed part when nothing the person said says they have something.
- **No part for the ground, the floor or the room:** validation drops it, with the mates and rules that name it
  (`plan.dropped`). **One part to build builds at once:** `P.buildable` counts parts to make, so a reference part
  doesn't stop the first run for review. The stool's step says "one part (the bathroom floor is what it stands on,
  not a part)".
- **One retry:** a refused plan goes back to the planner once with the reason, then falls back to one part. `=` in a
  rule says "`=` isn't a comparison; use `==`".
- **No tautologies:** a rule that calls no measure of a part and names no part ("shaft_d == 25.4") is refused.
- **Invented numbers are proposals:** `classify()` marks a skeleton number `stated` only when the person gave it (any
  unit: "1 in" is the planner's 25.4 mm), and a rule `stated` only when it reads stated numbers. Everything else is
  `assumed`, whatever the planner wrote, and not enforced: only `binding()` rules go into assembly.yaml. Review shows
  "assumed: not checked until you keep it" with **Keep** (`POST …/plan/checks/{id}/keep`). A revision doesn't undo
  a keep. design.js v=54.
- `tests/test_plan_live.py` (31; all fail on main). One #103 test now expects only the turbine's stated rule enforced.
- **Not done here:** the accept's live re-run of the three sentences. It spends Theo's key, so it needs his word in
  night shift's session (a relayed word doesn't count).
- **#123 review:** what it stands on is dropped only when its id's last word is a ground word and it isn't made
  (`floor_lamp`, `wall_shelf`, `ground_stake` stay; `bathroom_floor`, `garage_wall` go), and it's always said
  (the review reply, the card, the one-part step). Making is read from `made` only ("a Honda generator, built in
  2019" is still yours). A fixed part with no possession phrase near its own noun is **assumed**, "(you have it? say
  if not)", not a refused plan; "my kid's science fair" isn't having a generator. Keep marks its numbers kept (tested).

### 2026-11-07 · CALI-113 (#115) · A part with loads() is held to them, goal or none
- **Rule 6, found in #106's re-check:** a design whose parts have `loads()` but whose `scorecard.yaml` has no strength
  goal released "ready to cut" on a strength ✗. Only "your shop can make it" was scored. It hits designs made
  without goals: no key, older ones, a hand-made `scorecard.yaml`.
- **The scorecard now adds an implicit check** when no binding goal names strength: "holds what its loads say, at
  its factor (from its loads)", `strength.safety >=` the runs' own `min_safety`, `source: implicit`. It goes through
  the same rules as a stated goal:
  - a ✗ is a fail, so not ready;
  - "not trusted" (#96) and "not resolved" (#110) count as unknown, so not ready;
  - a strength check that couldn't run counts as unknown;
  - #106's middle-only `edge` applies once it's in `main`.
- **A stated strength goal isn't doubled.** A proposed one doesn't bind, so the implicit check still stands beside it.
- **Old designs** get the check the next time they're scored.
- Tests: `tests/test_implicit_strength.py` (the goal-less test stool at ✗ 1.46×: fail, not ready, and the book says
  why; light: pass and ready; a stated goal: no doubling). On main there's no implicit check at all. CI is the full
  run.

### 2026-11-06 · CALI-107 (#107) · A requested feature builds or the script says why not; the reply says what changed
- **`part_scripts.md`: no silent fallbacks.** A requested feature builds or raises with a clear message. No
  `try/except` that passes or hands back the shape without it, no returning the input because a size came out
  small, no clamping a requested size without raising.
- **The round checks it** (`fallbacks.find`, an AST read of the script; it never runs it), and fails naming each line:
  - an `except` (bare, `Exception`, …) around a CadQuery call that passes or returns something unchanged;
  - `min(<a requested size>, <a computed limit>)`, through a local copy too (`r = p["fillet_r"]`; tuple
    unpacking counts);
  - `if <a size test>: return <the input>` (a test against 0, "not asked for", is fine).
  - On copies of the bar stool's v4 to v6 it flags every fallback the issue names: the fillet's clamp and its two
    `except: pass`, the mesh's clamps, its two size-guarded returns and its `except: return cone_solid`. The
    samples and the suite's fixtures are clean.
- **The reply says what was asked for and what changed:** "Asked for: …", "Changed: wall 4 mm → 6 mm" (in inches too:
  "fillet_r 6.35 mm (1/4 in) → 12.7 mm (1/2 in)"), and the volume before → after. If the shape didn't change, it
  says what you asked for may not have happened. It says what isn't measured. "The part's own checks pass" replaces
  "Every check on this part passes", which read as covering the request.
- **From #119's review:**
  - a requested parameter (or its copy) compared with 0 or 1 is "none asked for", not flagged (`if p["holes"] < 1:
    return shape`); a computed size still is;
  - any handler type or tuple around a CAD call counts (`(ValueError, RuntimeError)`, OCP's `Standard_Failure`), and
    so does `return s.translate(...)`, the input moved without the feature;
  - a try/except around anything but CAD isn't flagged;
  - the reply says a parameter's plain name ("foot fillet radius") and every length with its unit, whole numbers too.
- **A failing check's reason now reaches the chat** (`_fail_lines` adds its detail), so the line is named there too.
- Tests: `tests/test_fallbacks.py`.

### 2026-11-06 · CALI-110 (#110) · The scorecard and the build book never call an unresolved ✓ a pass
- **The scorecard:** a strength check that would pass on a run whose FEA governs a ✓ it can't see the wall for is
  `unresolved`: never pass, counted with the unknowns (`summary["unresolved"]`), with the cards' own words as its
  note. A ✗ by its number stays a fail. `untrusted` (#96, a filled-in shape) is as it was.
- **So nothing downstream calls it ready:** the release isn't ready (`unknown` > 0). The book's header reads "Not
  ready — 1 not resolved", its scorecard table marks it "not resolved", and its *Will it hold?* row reads "not
  resolved: too coarse to see its walls". The Studies scorecard row isn't green ("· 1 not resolved"), and the
  release row says "not ready: a strength check isn't resolved". The page's scorecard shows "!" and "(1 not
  resolved)".
- **The design card's scorecard line** (#103's) names it "N not resolved", apart from "not checked yet".
- **The kid's book promises nothing on it:** no "It should hold…"; "Don't stand on it yet", for a grown-up.
- **From #111's review, four more places that said "holds"** on it, now fixed:
  - the 3D stress callout reads "not resolved: the FEA read 3.5x, too coarse to see its walls", with no breaking load;
  - `pictures.reply` (kid-facing) says a grown-up checks it again before anyone stands on it, and the turn isn't ok;
  - the history line reads "strength check: not resolved", because the study now records `unresolved` in the
    part's history;
  - the make card reads "not ready: a strength check isn't resolved".
- **The audit** (every reader of a strength run's verdict), each handling `unresolved`:
  - `answers`: both cards (#100);
  - `studies`: the load row (#100), the scorecard row and the release row (here);
  - `scorecard`, `release`, `kidbook` (here);
  - `chat._facts`: the raw numbers say "NOT RESOLVED…" (here);
  - `trials.predict`: the "Test it" prediction's basis says it's a rough guess (here);
  - the 3D callout, the history line, `pictures.reply`, `chat.picture`'s ok, the make card (#111 review);
  - not a strength-FEA verdict: the frame study and snow (beam models), goal labels, design-rule promotion;
  - `lighten` and `carve` stations: their own FEA runs, which this doesn't touch: #101 (CALI-106).
- Tests: `tests/test_unresolved_score.py` (main fails 4 of the first 6). `design.js?v=48`.

### 2026-11-06 · CALI-97 (#100, merged with main after #96) · "Not trusted" wins over "not resolved"; a ✗ stays a ✗
- **Merged `main` (with #96) into #100.** Where both reword one strength verdict:
  - the filled-in shape's "not trusted" comes first, because the check ran on a block, the more basic problem;
  - "not resolved" or "not checked" comes next;
  - a fail stays a ✗ under both.
- **A filled-in part that fails** now reads ✗ on the part card, the design card and the Studies row, with "It ran on a
  filled-in shape, so the part as built is weaker still". The block is stronger than the hollow part, so a fail on it
  is certain. #96 alone had read every filled-in verdict as a warn.
- **Page:** "not trusted" first, then "not resolved", then holds or doesn't. `design.js?v=45`.
- Tests: `test_filled_verdict` (both together on the design card and in Studies).


---

### 2026-11-06 · CALI-91 (#68) · Words leave the machine only when the person sends them
- **The 🎤 asks first** (rule 6). A browser's speech recognition sends the audio to its maker. On the first press:
  "Your browser turns speech into words by sending it to its maker (Google, in Chrome). Talk anyway?", with **Talk**
  and **Type instead**. The answer is kept in that browser's `localStorage`, every read and write in try/catch; if
  it's forgotten, it asks again. After Type instead, the next press offers the computer's dictation and a Talk button,
  and never listens unasked.
- **On the device, it doesn't ask:** where `SpeechRecognition.available({processLocally: true})` says "available", it
  listens with `processLocally` and nothing leaves. Checked on this machine: the app's browser pane (Chrome/152) has
  the API and reports on-device "unavailable", so it asks. Chrome and Safari themselves weren't checked.
- **The fallback names no machine it can't see:** "Use your computer's dictation: on a Mac, press the 🎤 key (or Fn
  twice)."
- **What's typed goes to Claude, said:** under the first-run box, and under the chat box until the first message is
  sent, when a key is set.
- **With no key, Build it says what's missing instead of failing:** "Building a new design needs a Claude key (see
  .env.example). Until then, open one of ours below." The API refuses a first build with a 409 in those words, the
  questions' Build it records the answers and starts nothing, and the page shows the line instead of the button.
- Tests: `tests/test_privacy.py` (node: `rec.start()` only after a yes or on the device; Type instead; the second
  press; cleared storage; blocked storage); `test_firstrun` (no key: no job, the 409). `?v=44`.
### 2026-11-06 · CALI-35 (#103 review) · A rule can't freeze the app, and a check that hasn't run is never a pass
- **A rule Claude writes can't run away** (blocker 1: `9 ** 9 ** 8 > 0` ran over 60 s under OCCT on every design
  load). The plan's validator allows arithmetic, comparisons, and/or/not, the measures, names and numbers. It refuses
  `**`, strings, lists, subscripts, keywords, any attribute but a box's sizes and corners, rules over 300 characters,
  and a rule that doesn't answer yes or no (`rotor_d`, `1`). The evaluator refuses the same, as a second guard:
  powers above 4, a repeated string or list, ints past 256 bits, private attributes, and over 2,000 steps, each
  checked before it's done. So no rule can hold the lock.
- **`bbox()` has named corners** (`max_z` and the rest). The planner had been told `.max.z`, which a bounding box
  didn't have, so every such rule would have errored. Now it's tested on a real box against the skeleton.
- **A check that hasn't run is never a pass** (blocker 2, rule 6). `Report.said()` and `waiting` are used by the
  header badge ("1 pass · 5 not checked yet", never "all checks pass"), the chat ("No design check has run yet: 3 not
  checked yet.") and the card ("No check has run yet: 3 not checked yet.", warn). `all_pass` keeps its meaning,
  because the authoring loop stops on it and a part spec's deferred check (a print time with no slicer) must not hold
  it forever. Nothing a person reads uses it alone.
- **The planner's fallback reason is plain words** ("skeleton 1 unit is missing"), never pydantic's text and URL.
- Tests: the reviewer's runaway rules (the validator and the evaluator), the box rule, `said()` cases, the header
  badge (node), the card, and a "?" that's actually sent during review.

### 2026-11-06 · CALI-35 (#3a) · The plan: parts, the numbers they share, the checks between them, reviewed first
- **`plan.py`:** a plan is parts (what each is, how it's made, `role: fixed` for what the person has, what it mounts
  on), the skeleton (named numbers with a unit and why), mates, and rules over part ids and skeleton names.
  - **Validation refuses, with the reason:** a cycle ("base → mast → hub → rotor → base"), a part, mate or rule
    naming something the plan hasn't, a skeleton number with no unit or a unit Caliper doesn't measure in, a rule
    calling anything but the assembly's measures, two things with one name.
  - **The build order:** mounted-on first, the plan's own order otherwise.
- **The planner:** one Claude call with the plan's schema as its only tool. The system prompt carries the spec's rule:
  separate parts are made separately or move; pieces of one sheet or printed part stay one part.
- **The first run plans first** (with Claude):
  - a plan of several parts is saved and the run stops for review: "A wind turbine in 4 parts: the rotor (…), the
    hub, the mast (…) and the base (…)";
  - a one-part plan (the stool) builds as today;
  - a plan that can't be used is refused, and it builds as one part, saying why;
  - with no key it builds one part, as today, and says planning needs Claude.
- **Build it on a reviewed plan:** "The plan's saved: 4 parts. Building them one by one, in order, comes next (#3b)."
  Nothing is authored (the foreman's call: 3a builds nothing past today's one part).
- **Saved** in `assembly.yaml` (the planned parts at their script paths, the mates as `plan_*`, the rules) and
  `design.yaml` (`skeleton:`, and `plan:` with its parts, order and status).
  - Evaluation skips planned parts that aren't built yet, and a rule naming one is deferred: "waits for mast to be
    built". Every other part loads as ever.
  - A rule can read skeleton names (lengths in mm) and `abs`/`min`/`max`.
- **The review:** the plan on *What is it?*, and the parts in build order, the numbers in the person's units and the
  checks under *the numbers*.
- **The chat edits the plan during review,** never the geometry: "make the mast 10 ft" → "Changed the plan: mast top
  z: 7 ft → 10 ft." A question is still answered.
- **Not done: the live run** of the three sentences (turbine, camper, stool). It spends Theo's key, so it needs his
  word in the session that runs it.
- Tests: `tests/test_plan.py` (a stubbed client throughout).
### 2026-11-06 · CALI-101 (#93) · Carve it: one click, one carve, its progress, and a cancel
- **The page error on Theo's run** ("Cannot read properties of undefined (reading 'ok')"): `makingView` read
  `m.data` while the shop plan was still loading. It says "planning…" until it's back.
- **One carve per design at a time,** checked as it's queued (`JobRunner.submit(exclusive=True)`, under the runner's
  lock), so two requests 11 ms apart can't both get through. The second gets a 409: "a carve is already running: step
  2 of 6". The page keeps the carve in `S.carveJob` from the click, so a second click (or a second handler) sends
  nothing.
  - **Why one click sent two:** not found. The page draws one Carve button and wires it once. Both guards now stop
    a double-fire whatever its cause.
- **The panel shows the carve as it runs:** the step it's on, the bar, "about N min left" from its pace so far, and
  **Cancel**. A redraw draws it again from state; a reload finds it through `design.carving`.
- **Cancel:** `POST /api/jobs/{id}/cancel`. A queued job never starts. A running carve stops at its next step
  boundary (in the sweep, or between steps) and keeps what it finished: #99's record, marked `cancelled`, with the
  best of its steps. The panel and the Studies row say "cancelled after k of n steps".
- **The label before you press** (reworked from #102's review). Until a carve of the part has finished, it's a floor:
  "at least about N min at this size". That comes from this version's default-voxel strength check (the coarsest at
  this version: a finer one asked for never sets it), × 45, the low end of what was measured: 47 on the printed box,
  67 on the mixed stool, about 65 on the bar stool's sweep, about 190 on the reviewer's tube. A ratio isn't a
  constant, so it never says "about" before a carve has finished. After one, it's that carve's own time. With no
  check: "check it holds first". With a check whose voxels didn't connect: "a carve can't run".
- **One step count:** the carve says "in 7 steps (as drawn, then 6 carved)". The panel, the 409 ("step 3 of 7"),
  the cancelled panel and the Studies row all count the same 7.
- **"Stopping…" survives a reload:** `stopping` is in the job's `to_dict` and in `design.carving`, and a cancel of a
  running job emits a `stopping` event, which a page that follows the job from the start hears.
- Tests: `tests/test_carve_click.py` (main fails 7 of the first 9; the makingView one with Theo's exact error).
  From #102's review, tests that can fail: a barrier hook between the check and the queueing (a check-then-queue
  split queues two); and node tests for the click guard, "stopping…" after a reload, following a running carve, and
  the label's cases. Each fails under the mutant the reviewer found surviving.
### 2026-11-06 · CALI-97 (#100 review) · Four across, a budget for the finer run, and a ✗ stays a ✗
The reviewer's 5 findings and the foreman's 10 items on #100.
- **`RESOLVE_MIN` is 4** (the foreman's call from #100's own table; still NEEDS ENGINEER CHECK for #42).
- **A finer run is capped by a voxel budget:** `finest()`, 8× the default's voxels (`FINER_BUDGET`, twice as fine
  each way). An asked-for `spacing_mm` finer than that runs at the finest it may, and says so. Where even that can't
  get 4 across the wall, no finer run is offered, and the card says: "Not checked: its walls are too thin for the
  voxel check at this size. A hand check or a printed test piece is the way to know."
  - **Judgment call:** the review said "the same budget" as the default. With `VOXELS_THROUGH` 4 = `RESOLVE_MIN` 4,
    a default run is only unresolved when that budget already bound it, so a finer run inside the same budget could
    never be offered. 8× keeps the button meaningful and bounded. `FINER_BUDGET = 1` is the other reading.
- **The wall that gates a verdict is the thinnest** (the reviewer's blocker on d82c67e). A 10th percentile let 5 mm
  voxels "see" a spool hung from a 0.6 mm neck and call it ✓ 9.7× at 10 lb (main: ✗). Back to `min_wall_thickness`;
  where the thinnest spot is only a lip (the bar stool's 0.3 mm), the cap says "not checked", the safe side.
- **A ✗ stays a ✗,** with "The fail may be the model's: the voxels can't see its … walls." on the part card, the
  design card and the Studies row. Only a ✓ turns to warn.
- **Walls in a unit that doesn't round them away:** 1/32 in fractions, or mm under 1/32 in ("0.3 mm", never "0 in").
- **The numbers panel:** amber "not resolved" / "not checked" badges in place of a green "holds", in the case, the
  run's header and the run picker; the case says "The FEA read Nx at voxels of …, too coarse to see its … walls".
- **The finer run's time** comes from the run's own FEA time per voxel, scaled as voxels^(4/3): measured on the tube
  and the box stool, time per voxel grows as about the cube root of the voxel count.
- **No time for a finer run when the coarse run didn't connect** (the reviewer: "about 1 min" on the bar stool copy, for
  a run that took 39): its FEA stopped at once, so its time says nothing. The button reads "(how long: unknown)".
- **The spacing clamp is pinned by an assert:** an asked-for 0.1 mm reaches the voxelizer as the finest the budget
  allows (whittle's LoadStudy stubbed, so a mutant fails on an assert, not by running away).
- **Run ids sort by `created`** (`runs.newest_first`), the id as tiebreak, in every listing (loads, carve, lighten,
  aero, frames, gussets, whittle, patterns, cut plans) and in a saved sample. This was the reviewer's
  `test_resolved` flake.
- **The teardown judges only its own test's jobs** (a snapshot at setup); `CALIPER_JOB_GRACE` sets the wait.
- **The API's 0.1–50 mm bound is pinned** (the reviewer's surviving mutant now fails).
- **On the 0.01:** the id sort can't explain it. That test reads `study()`'s return value, never a listing. See #100.
- Tests: `tests/test_resolved.py` (the spool; the `across` allowance and an 8× budget that really binds: two
  mutants that survived), `tests/test_run_order.py`, `tests/test_jobs.py` (the reviewer's three-test leak, under
  pytester).

### 2026-11-05 · CALI-97 (#80) · A ✓ can't rest on an FEA too coarse to see the wall
- **Rule 6, found on Theo's bar stool:** "✓ … 2.58x", governed by the FEA at 4.6 mm voxels across a 3.9 mm printed
  wall.
- A study now records its thinnest wall and whether the FEA resolved it: 2 voxels across, for now (NEEDS ENGINEER
  CHECK; #42).
- When an unresolved FEA governs, both cards read warn: "Not resolved yet: the check was too coarse to see its 4 mm
  walls. Check it again finer." A button runs it finer, at least 2 voxels across, and says roughly how long.
- The design card's strength lines say "about" when the printed model governs.
- **Before and after, on the printed fixtures:** only the 1-voxel-across verdicts change (✓ → warn).
- **For #42:** the printed box reads ✓ 2.7× at 2 voxels across and ✗ 1.9× at 4, so 2 is too few to trust a verdict.
- Tests: `tests/test_resolved.py` (main reads ✓ on both cards for the coarse tube). Commit: `caf174e`.
### 2026-11-05 · CALI-96 (#78), #96 rework · "Not trusted yet" everywhere a filled part's strength shows
The foreman's six items. The rule: wherever a strength verdict rests on the filled solid, it never reads holding.
- **The scorecard** grades it "untrusted", so the build package isn't "ready to cut". `d5a66fd`
- **The numbers layer and the 3D view** say "not trusted: a filled-in shape": the panel header, the case badges,
  the heat callout, the lightening line and the step previews. `b3adda5`
- **The cache fails closed:** "couldn't check its shape" is never holding, and isn't kept. `79fe045`
- **The kids' book:** no stand-on-it page; "Don't stand on it yet: a grown-up checks it first". `c349f75`
- **The design card** leads with the verdict, with the check's name after. `85bc844`
- **Studies and Lighten** read the part as it is now, so old runs say so too. `be73bd1`

---

### 2026-11-05 · CALI-96 (#78) · A strength verdict on a filled-in solid reads "not trusted yet"
- **Rule 6, found on the owner's step-stool-2 after the ship.** *What is it?* said `build()` was filled in, while
  *Will it work?* read "✓ Holds kid + dad (250 lb), 2 times over" from a check that ran on that block.
- `consistency.filled(store, pid)` (cached per version and script) now says when a part with `loads()` fails the
  volume check by being filled in. When it does:
  - both cards' strength lines read warn: "Not trusted yet: the strength check ran on a filled-in shape, not the
    step stool as built. Fix its shape first …";
  - the build book and the kids' book don't print a holding line;
  - a study on it says, in its record, notes and headline, that the number is the block's.
- Tests: `tests/test_filled_verdict.py`, written first and failing on main (the filled box read "Holds …, 3.1
  times over"). On the owner's design, read on a copy: main shows ✓, this branch shows warn on both cards.
  Commit: `53f1067`.

### 2026-11-05 · CALI-103 (#95) · The app no longer crashes when the page and a study query one mesh at once
- **The owner's app died three times (exit 134/139) in libspatialindex:** two threads in one cached mesh's R-tree,
  once with no study running (just the page's burst after a revision).
- **`caliper/spatial.py` holds one lock for each trimesh spatial query** (`contains`, `closest_point`,
  `signed_distance`, `nearest`, `ray`, proximity), never across a loop or a study step. Every caller goes through
  it, and a guard test fails if any module queries a mesh another way.
- **Measured:**
  - a raw two-thread race died in 7 runs of 7; through the lock it survives;
  - a server on `main` died (exit 139, the same stack) 32 s into a page burst during a carve; the fixed server
    survived 6 minutes of it;
  - during a real carve, a card request took 0.99 s median and 2.58 s worst (97 requests), against about 1 s idle.
- **A crash eats less work:** a chat message is logged the moment it arrives, and a carve writes its run as it goes
  ("not finished: 1 of 3 steps checked").
- Commits: `6b0535f` (the lock), `2044258` (the message), `e3a5151` (the carve's progress).

---

### 2026-11-01 · CALI-87 (#63), #75 rework · The reviewer's review of #63, worked
New commits only, on `cali-87-correctness`.
1. A regression from finding 9: the kids' book crashed when certain pieces shared a name (8 of 26 ways), and
   the package shipped without it. The chosen piece is now taken out by identity, and all 26 make a book with
   18 screws. `edc63e0`
2. A kids' book that fails is said in the package's notes and kept for a report. `cb45cae`
3. Pages tell same-named pieces apart: drawings by key, "the first side" / "the other side", "touches both
   sides". `23e9025`
4. A filled box caught by its core reports the core share against 10%. `21cf8f3`
5. A lightening study is adopted only onto its own version (409). `64d1b6b`
6. A chat turn that fails still answers in the log. `d492d90`
7. The carve refusal names "roll it back". Lightening a carved part is refused before the study runs.
   `5314c0f`

### 2026-11-01 · CALI-86 (#62), #71 rework · The reviewer's review of findings 8–13, worked
The foreman's ten items. New commits only; the reviewed ones keep their hashes.
- **2 (rule 6):** a live test that broke below what the part must hold, or sagged well out of the predicted
  band, outranks the prediction. The part card loses its ✓ lines, and the design's strength checks read the
  test: "It broke at 150 lb in your test. We predicted it would hold 400." `57e9568`
- **3, 4, 7:** every step is judged and the worst governs (closes #70 #1). Each edge is pinned by a test. A
  break within 10% of the prediction matches it; short of that is "our check was too hopeful"; a low sag is
  "stiffer than our check said". `c88a047`
- **1:** the promise follows only strength and frame verdicts (`rests_on_model`), and goes in the first-run
  reply and `chat._facts`. `56e7eeb`
- **5, 6:** "about" follows the printed model where it governs (`load_study.rough`); a plywood-governed verdict
  keeps plywood's words. The top line is "Holds a foot, about 2.6 times over.", with the caveat by the promise.
  "About" is also on the carve reply and the release table. `2f59997`
- **8:** an old carve run says "of the whole solid (carved before CALI-86 …)", never relabelled. `a59f9f4`
- **9, 10:** the chat turn isn't ok when the check couldn't run; each sample guard is tested alone; an unknown
  sample is a 404 with no path.

### 2026-11-01 · CALI-86 (#62), #69 rework · The reviewer's review of findings 1–7, worked
The foreman accepted every disagreement in the reviewer's review of #69. One commit per item, new commits only
(the reviewed ones keep their hashes).
1. **(rule 6)** The beam now takes where the foot is. Near a free end the width is no more than half the
   effective width plus the foot's distance from the end (BS 8110; NEEDS ENGINEER CHECK, with the DIN Heft 240
   note): 190 mm, not 280, for a foot at the end of a 900 mm panel. The tests go through `plate_check`.
   Centred loads are unchanged. `13460bd`
2. The report scrubs anyone's home folder. A 500 says a plain sentence and the error id. A YAML error keeps
   its line and column, never the excerpt (the reviewer's "a surprise stool for Emma"). Failed jobs go the same
   way. The dialog now says what's true. `fe3c39e`
3. Trial steps, the log and part histories are read defensively. A bad line is left out and counted, never a
   500, and the API takes `true` as no number. `d37c422`
4. A sample is saved beside the old one and swapped in, so a failed save leaves it whole. `1e42dfe`
5. The pattern tests cover the front and back panels (the x-only mutant fails them). Titles print without an
   em dash (a test renders each character). `9c6765b`
6. The carve line names which part holds. The headline reads the step it names, and when carving makes the
   whole part fail, the headline says so and isn't green. `02bd3d8`
7. **(rule 6)** In the kids' book, the kid stands an arm's length behind and never in front of the saw, with
   ear defenders. The wood is clamped with the line past the table's edge. The grown-up stands on the new stool
   first. `95369a3`

---

### 2026-11-01 · CALI-87 (#63) · The reviewer's correctness findings on the open stack, fixed
Stacked on #58 (which is on #62). One commit per finding, each with a test seen failing first.
- **1 (#57):** the printed rest was cached per version, not per what-if, so a 3/4 in what-if left the part as
  drawn with the what-if's sides. Now it's keyed on the declarations too. `1a8337a`
- **2 (#57):** every script writer (BUILD what-if, frame, gussets, drag, refine) now drops a carve through
  `carve.uncarve()` and says so. A picture or lightening on a carved part is refused, with the reason. `7c83d87`
- **3 (#57):** a carve of an older version isn't adopted (409). `b829d70`
- **4 (#57):** two test assertions that couldn't fail now can, and each was made to fail on purpose. `e21a9f6`
- **5 (#50):** "the right side" cut the left. A side named outright now wins over "side". `5fe022b`
- **6 (#50):** a NaN pad point is refused (422), and a failed picture job still logs a reply. `3bf812f`
- **7 (#49):** the cut sheet now cuts holes before outlines, in SVG and DXF (Caliper's driver; no
  unfold-to-sheets change). `bbd87b4`
- **8 (#49):** a pinned size (`==`, made a band by measuring allowance) is checked for conflicts again.
  `071a3a9`
- **9 (#52):** joints are keyed by piece, not by name. Two pieces both called "side" were 16 screws in the BOM
  and 22 in the kids' book; both now say 18. `720e5c7`
- **10 (#52):** the build book lists `kids.html` only when one was made. `2d593ee`
- **11 (#56):** a small filled box is caught by the share of solid in no piece (more than 10%), not just by
  the volume ratio. `54c9fe5`

### 2026-11-01 · CALI-84 (#58) · One rule for where a load lands
- **Found in the walkthrough:** Theo's printed two-step stool passed `loads_land`, then its strength check said the
  foot "pushes on thin air". The foot's box was at the top's height, 1.2 mm above the floor of the 1/8 in mat
  recess. `loads_land` passed anything within about 2× the measuring tolerance, while the strength check reached
  one voxel. So they disagreed, both ways, depending on the voxel size.
- **Now one rule:** `load_study.touches(mesh, box, reach)`: the box is in the part, or within
  `reach = max(voxel, tolerance)` of its surface, with the voxel size from `study_spacing()` exactly as the study
  uses it. `loads_land` and `prepare` both ask it, and a miss fails both in the same words (which load, how far
  from the nearest surface). The strength check grows a box by reach plus half a voxel, so whatever passes has
  voxels under it. `held()` boxes use the same rule, and the authoring sandbox now reads `held()`.
- **Verdicts unchanged** on STOOL, BOX_STOOL and MIXED at 2 and 4 voxels through. The FEA moved ≤ 2.6% in safety
  and ≤ 4% in sag (2 vs 4 voxels through differ by 30–50%). `loads_land` on a printed part costs about 0.1 s more
  (it measures the thinnest wall for the voxel size).
- **On Theo's stool:** the adult's foot now lands. The child's box on the "lower step" really is in the air: the
  script's lower step is a box inside the upper body, so it adds nothing. Both checks now say so.
- Tests: `tests/test_load_lands.py` (12, written first and failing on the old code: the recess case passed
  `loads_land` and then raised in `prepare`), plus the strength suites. Commit: `06bd8db`.

---

### 2026-11-01 · CALI-86 (#62), findings 8–13 · The reviewer's findings on the open stack, fixed (part 2)
Stacked on findings 1–7. One commit each, each with a test seen failing first.
- **8 (#57):** "% carved away" counted the plywood the carve keeps: 30% was 46% of the print. Now it's the
  printed part's share, and labelled so. `663f332`
- **9 (#57, rule 6):** a printed part's verdict now says "about … (printed parts are a rough model)". `9aacd52`
- **10 (#50, rule 6):** with no strength check installed, a picture on a part with loads() got a ✓. Now it
  says it couldn't check, and isn't ok. `622c402`
- **11 (#51, rule 6):** breaking below what the part must hold is bad, breaking short of the prediction is warn,
  and a sag more than 2× outside the predicted range is warn, with words. `2c041c2`
- **12 (#43):** `open_sample("..")` copied the package folder. Now it takes only a listed sample's slug.
  `258fe5e`
- **13 (#43):** scorecard verdicts (the camper's "safe to tow" lines) now carry the promise. `0b21850`

### 2026-11-01 · CALI-86 (#62), findings 1–7 · The reviewer's findings on the open stack, fixed
The reviewer's pass over #43–#57, checked by the foreman. One commit each, each with a test seen failing first.
- **1 (#57, rule 6):** a panel on two edges spread a foot over its whole width, so a 900 mm × 1/2 in panel over
  300 mm read 2.72× when a plate solution says 1.11×. Now it uses BS 8110's effective width (the load's width +
  0.6 of the span), which reads 31% high on 900 × 300 and 23% high on 450 × 300 against a Lévy plate series. That's
  the safe side, the owner's call. Every stool fixture's verdict is unchanged. `136a5ef`
- **2 (#57, rule 6):** the carve's headline was green ("still 8.4x") while the whole part was 0.66×. It now leads with
  "doesn't hold as it is" and isn't ok. `8c70418`
- **3 (#43):** a failed chat job was kept with the person's message, and a design's folder named it in tracebacks.
  Jobs are now kept by kind, and a design's name is written `designs/<design>`. `report()` looped forever on a long
  error; now it always stops. The dialog now says what the report really holds, and a job is marked failed only
  after its error is kept. `cccc696`
- **4 (#43):** `caliper sample save` with no name deleted every sample. A name must now be a plain slug. `6b998a2`
- **5 (#51):** one NaN test step broke the design's page. Steps must be real numbers more than nothing, and a bad
  line on file is skipped (the panel says so). `4f51df6`
- **6 (#52, rule 6):** the kids' book had a kid holding the work while the jigsaw ran. Now the grown-up clamps,
  cuts and drives the screws, and the kid stands back in safety glasses. `b3def7e`
- **7 (#50):** the left side's pattern was mirrored. Patterns are now drawn from the outside face, turned rather
  than flipped, and each page names the face. `06092c7`

### 2026-11-01 · The firm · Caliper runs as a team of agents
- **Theo:** "please take on the foreman role found in ~/githubrepo/the-firm, and work with caliper-reviewer to
  review current PR's and existing work… also, you will be working with caliper-nightshift as your engineer".
- `firm/`: the roster (foreman, night shift, reviewer staffed; Socrates and marketing not yet), the stages
  (`stage: design → questions → ready → review`, now labels on the board with `in-progress`, `needs-owner`,
  `background`, `size:`), the seven rules with a draft rule 6 for Theo to decide (#60), one checkout per seat
  (the owner's checkout runs the live app on :8011; night shift 8016, reviewer 8017, each with a scratch designs
  folder), and Theo's conventions (CALI-N titles, LOG and DEMO entries) winning over the firm's defaults.
- First work through it: the open stack (#43 → #57, plus whittle#4 and unfold-to-sheets#2) routed to the
  reviewer; #58 (CALI-84, a load that passes loads_land and pushes on nothing) and #59 (CALI-85, the strength
  check's benchmarks, #42's first slice) designed and ready for night shift.

### 2026-10-30 · CALI-81 (#53), CALI-82 (#54) · Printed parts checked; a plywood top on printed sides, carved
- **Theo**, mid-walkthrough: "what I was specifying was a plywood top and printed sides since the sides would work
  in compression and we could whittle them down more interestingly". The designer had printed the whole stool, the
  strength check couldn't analyse a print (no material), and first run hid that behind a "Check it holds" that
  failed the same way.
- **Printed parts (#53):** `load_study.printed_material()`, whittle's PETG/PLA at the share that's plastic (1.2 mm
  walls + infill) and at half strength across its layers. Voxels are sized from the part's thinnest wall. Labelled
  rough, on the safe side, until a printed test piece says (#42). A check that can't run is kept in the part's
  history, and the card and first run's reply say why. (Theo's printed stool couldn't be checked anyway: its loads()
  put the foot on the hand-hold slot.)
- **Mixed construction (#54, slice 1):** `{"kind": "printed", "rest": true}` is everything in the solid that isn't a
  declared sheet or stick. `construction.printed_solid()` is the part less its sheets and sticks (manifold), cached by
  script; weight, shopping list and the printer (just the sides, split to fit) read it. Consistency checks only that
  the pieces are inside the solid. The designer's reference says when to use it.
- **Two materials (slice 2):** greentheo/whittle#4 gives `VoxelFEA` a stiffness per voxel (element stiffness,
  preconditioner, energy and stress all scale; 189 tests pass), and `WHITTLE_REF` is pinned at its commit `65e7e59`.
  Voxels in a sheet or stick are that material, the rest printed, each judged against its own strength; an older
  whittle analyses at the printed stiffness throughout and says so. The plywood top's plate check uses plywood and
  counts an edge held where the printed solid is under it.
- **A beam check:** a panel held on two opposite edges (a top on two sides) is checked as a simply supported beam, the
  safe side, as the plate check is for one held all round. Before, the FEA judged it alone, reading stiff (its sides
  clamp it) and taking plywood along the grain. It says how much stronger it is with the face grain across the gap.
  It changes one verdict in the tests: the 14 × 10 in top on two sides, 3/4 in, is 1.5x across the grain and 2.9x
  along it, not the FEA's "over 2". A 1/2 in top over 12 in on two sides, as Theo specified, doesn't make 2x either
  way: the weak link a carve can't fix.
- **Carve (slice 3, `carve.py`):** whittle's sweep on the printed voxels only (the wood, where it's pushed and where
  it's held kept; any printed surface may open), each step judged by the strength check in both materials. The chart
  is the printed part's own safety and stops where it runs out; the whole part's is beside it, and a part that
  already fails in its wood says so first. Using a step writes the shape as the part's: the wood exact from the
  script, the carved rest less a lip round the wood (half a voxel proud), kept in `carved/` and named in the script
  (`CARVED`); `assembly._build_py_local` builds the part from it, and a chat revision drops it and says so.
  On a test stool (1/2 in plywood top on 20 mm printed sides, a kid stepping up), 3 minutes at 6 mm voxels: the sides
  go 13.6x → 15.1x → 8.4x as 40% is carved away, 644 g less filament, then come apart. The carved legs come out as
  arches with a foot rail along the floor, the plywood top exact, one watertight body.
- **The page and the chat:** **Carve it** under *Will it work? → the numbers* for a printed part, the chart, a
  preview ("Preview, not carved yet") and **Carve it like this** (then the strength check again); "carve the sides";
  the studies page lists carves.
- **A crash it found:** three requests for a mixed part's cards, making and balance at once ran manifold3d booleans
  on three threads and took the server down (SIGABRT), as OCCT did before it got its lock. Every manifold boolean
  now takes that lock.
- Tests: `test_printed_strength.py`, `test_mixed.py` (the printed rest is the solid less the plywood; the printer gets
  only the sides; its declarations check; two materials, with and without whittle's stiffness per voxel, and the
  beam; the carve: a top that fails says so, the sides carve down until they don't hold, using a step rebuilds it
  watertight with the plywood unchanged, a revision drops the carve; a sheet part can't be carved; the chat routes
  carve to a printed part only; carving through the API), `test_load_study.py` updated for the beam.
- Live check in a scratch app (port 8015): the carved stool in the viewport, the carve panel and its chart, a step's
  preview and **Carve it like this**.
- **Full suite: 543 passed** (with whittle at `65e7e59` and unfold-to-sheets at `8fc66c9`); after the lock fix, the 84
  tests it touches pass again.

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

### 2026-10-30 · Decision · V1 as a hosted web app with a native wrapper, not the App Store (CALI-58, #7)
- **Theo:** "for app store, I'm thinking that no it's probably not going to work, and honestly, trying to make it work
  is going to add a lot of complexity. What we might be better off doing is creating this as a web app and service
  (Railway?) and then doing a wrapper around it. Obviously needs to be more than just a wrapper to a webservice, so
  we can add a few distinguishing features, but ultimately no code will need to be run on the user side. This of
  course, is going to present a compute bandwidth problem since FEA can be compute intense. perhaps that would be
  something we can keep local... dunno"
- What it changes: generated code runs on the server, so the real sandbox (CALI-66, #26) becomes multi-tenant
  isolation; accounts, storage and the API key move server-side; error reports (CALI-59) can go to the service with
  the person's say-so instead of a GitHub issue. Open: where the FEA runs (a worker pool, or the wrapper's own
  fixed, signed code on the person's machine) and what the wrapper does that the web page can't.
- Not started: needs a spec (`specs/`), then #6 and #7 rewritten to match.

### 2026-10-30 · CALI-79 (#47) · A build book a kid can follow: pictures first, one step a page
- Showcase 1 (#10) asks for a build book a kid can read, pictures first. The shop's book had two steps for the
  stool ("End and side panels", "Finish"), and its panel step said to "glue them to the floor's edge and the
  skeleton with foam-safe adhesive": the camper's words, for a plywood stool.
- **`kidbook.py`:** `kids.html` in the build package, for a build that's all wood (sheets or sticks, glued and
  screwed; a welded frame stays in the shop's book):
  - **Get your things:** the shopping list in a kid's words, plus the tools, as boxes to tick.
  - **Draw the pieces:** each pattern's thumbnail and its name, and the full-size PDF.
  - **Cut them out**, with a grown-up: for a picture or a hole, "drill a hole just inside the line first".
  - **Sand the edges.**
  - **One page a piece**, in the order they go together: the lowest standing piece first, then each one that
    meets what's there (the joints the shopping list counts screws for), lowest and biggest first. Every page has
    the same view, what's on in pale and the new piece in colour, and "Put glue on the edges where the left side
    panel touches the front panel… put in 2 screws." The pages' screws add up to the shopping list's.
  - **Paint it**, if it's painted.
  - **Test it:** gently, with a grown-up holding it; how many times over it should hold; what that promises.
  - The view looks at the side with the picture (and the front with it); the cover is the stool with its T-rex.
- **Drawings show holes:** `release.pieces` gives a flat panel its holes, so the shop's book draws the T-rex and the
  lightening windows too. *How do I make it?* links **The kids' build book** beside the build book.
- Tests: `test_kidbook.py` (a wooden build gets one and a welded frame doesn't; the pages in order with the top
  last, a kid's words, the start-hole line, the promise, a drawing per piece, the screws adding up; the drawings
  show a panel's holes and look at the picture).
- Commits: `14d939d`, `96584bf` (the shop book's wood panels). PR #52. **Full suite on this branch, the stack's top: 530 passed.**

### 2026-10-30 · CALI-80 (#48) · Record the test: predicted against measured
- Showcase 1 (#10): "Dad stands on it, then sandbags go on until it breaks. Record the predicted vs measured here."
  Also the first real point for calibration (#42).
- **`trials.py`:**
  - **The prediction**, from the latest strength check on this version: for the worst load, the sag at the
    middle of the panel it's put on, at each step (50 lb at a time) up to where it should break, as a range.
    The range runs from the FEA's sag (joints solid: the stiff end) to the plate check's (edges free: the
    flexible end), linear in the load.
  - **What to measure it with:** the stool's top under 200 lb should sag 0.003–0.005 in (0.08–0.13 mm). A tape
    measure won't see that, so it says to use a dial indicator, or a straightedge and feeler gauges.
  - **The record:** each step in `trials/<part>.jsonl` (load, sag, broke, note, the version).
  - **On the card:** "Tested: it held 400 lb, sagging 0.006 in (we predicted 0.004–0.008 in)." or "Tested: it
    broke at 1,100 lb (we predicted about 1,240)." A test of an older version reads as stale.
- **Test it** under *Will it work? → the numbers*: what to do and with what, a chart of the predicted band with
  the measured points and where it should break, the step table, and a row to record a step.
  `GET/POST /api/designs/{slug}/parts/{pid}/trial`.
- Tests: `test_trials.py` (the prediction from the load to where it breaks, as a range, and what to measure with;
  none without a check on this version; steps kept and compared, the card's line, where it broke, an older
  version's test reads as stale; the API).
- Commit: `b957193`. PR #51.

### 2026-10-30 · CALI-78 (#46) · A picture on it: a T-rex cut out of the side, and it still holds Dad
- Showcase 1 (#10): "a stool to reach the sink, with a T-rex on it". The kid's ask is the hook; the engineering
  question it raises is the story: can you cut a T-rex out of the side and still hold Dad?
- **`pictures.py`:** the picture comes from words or from the pad.
  - **Words:** a hand-drawn T-rex is built in (also "dinosaur"). Anything else, Claude puts together from simple
    shapes (ellipses, thick strokes, polygons), joined and smoothed into one silhouette. Asked to trace an outline
    point by point, its T-rexes came out unrecognisable and one crossed itself; built from shapes, its cat and its
    rocket came out right (its T-rex still didn't, hence the built-in one).
  - **The pad:** a drawing, screen y down.
  - **Where it goes:** a panel nobody stands on (the front, or the one named; "side" means left or right), upright
    and facing the way it was drawn as you look at it from outside, centred at the room's pole of inaccessibility,
    90% of as big as fits inside the 1.5 in rim and a web clear of any holes.
  - **Cuttable:** closed and opened at 1/8 in radius (nothing narrower than a 1/4 in blade turns round, no gap
    narrower), exterior only (no eye to fall out).
  - **Checked:** the strength check is tried with its cells taken out of the voxels (as the lightening study does);
    too weak, it shrinks by 0.8 up to five times, or says it can't and changes nothing.
  - **Cut:** written into `HOLES` with `"picture": "T-rex"`, so the patterns, the CNC sheet (CALI-77) and the
    rebuilt part's strength check see it. That check is the number the reply gives.
- **Lightening leaves it alone:** `holes.merge` marks picture polygons and `lighten.panels` keeps a web of wood round
  them, so a later study doesn't read the T-rex as a hole and redraw it as a blob; `lighten.adopt` keeps picture
  entries and replaces only the lightening holes (`holes.read`/`holes.write`, shared now).
- **From the chat:** a new route, `picture` ("put a T-rex on the side"). Claude routes it with the subject and the
  panel; offline it's taken only for a shape it can draw or one called a picture, so "add a foot on the bottom" is
  still a part. **From the page:** **🦖 Put a picture on it** under *What is it?* (a part, or a one-part design):
  say it (or 🎤), or draw it on the pad, pick the panel, **Cut it out**.
  `GET/POST /api/designs/{slug}/parts/{pid}/picture`.
- **Live (the sample stool, Claude routing):** "put a T-rex on the side" → "✓ I cut a T-rex 5.2 × 5 in out of the left
  side panel. It still holds, 3.11 times over (it needs 2)." in about 40 s. The side's pattern shows it with "drill a
  3/8 in hole inside the line to start the jigsaw"; *How do I make it?* reads "5 pieces, 1 hole".
- Tests: `test_pictures.py` (the built-in T-rex and Claude's shapes joined; what a jigsaw can't follow smoothed
  out and the eye dropped; panels nobody stands on, upright as seen from outside; a T-rex on the side cut and still
  holding, on the rebuilt part; lightening leaves it alone and adopting keeps it; too weak shrinks it, hopeless
  changes nothing; the chat routes it and leaves parts alone; a drawing from the pad cut through the API).
- Commit: `c2ecdc0`. PR #50. **Full suite: 523 passed.**

### 2026-10-30 · CALI-76 (#44), CALI-77 (#45), CALI-68 (#28) · Three leftovers: fast cards, holes on the CNC sheet, measuring error
- **Theo:** "Please do the seven PR merge stack. Then Showcase 1 and the three leftovers." The stack (#25, #30, #33,
  #35, #36, #37, #41) is merged into `main` in order, each retargeted to `main` and merged with a merge commit;
  nine issues closed with it (#1 stays open: #30 was one slice). #8 went up as PR #43 into `main`.
- **Cards in under a second (#44):** one set of four cards ran `construction.declared()` nine times, each the part's
  script in its own process (~1.5 s), always on the same script: 13.4 s of 13.4 s on the stool. Now cached by the
  script's text and BUILD what-if (a change to the script is a new key; callers get a fresh copy): 0.9 s.
  `design_state` on a warm server is 6 ms.
- **Holes on the CNC sheet (#45):** a holed panel goes to unfold-to-sheets as triangles round its holes
  (`cutplan.holed_face`: manifold3d triangulates it in the outline's plane, wound as the outline faces), so the
  unfolder reads them as the piece's inner boundaries and cuts them. The note now says to cut the holes before the
  outlines. **A bug it found in unfold-to-sheets:** a piece was lined up by the principal axes of all its points,
  so an off-centre hole tilted it on the sheet (0.13° for a 2 in hole; a rounded window, more).
  greentheo/unfold-to-sheets#2 lines a piece with holes up by its outline (one without holes as before; 145 tests
  pass); `UNFOLD_REF` is pinned at its commit `8fc66c9`. Theo's own checkout (`vendor/` links to it) needs that PR
  merged and pulled before the new cut plan test passes locally.
- **Measuring error (#28):** a drafted rule on `min_wall` or a `bbox` size has the measurement's tolerance written
  into it (`promote.MEASURING`: a wall 0.15 mm, a size 0.1 mm, from the 0.05 mm tessellation and the ray-cast):
  `min_wall >= 19.05 - 0.15` holds for 3/4 in ply measured at 18.98 and still fails 5/8 in. An `==` on a size
  becomes a band. The offer says what the allowance is; `_bounds` folds the arithmetic, so contradictions are
  still caught.
- **Filed for Showcase 1 (#10):** CALI-78 (#46) a picture on it (the T-rex, cut out and still holding Dad),
  CALI-79 (#47) a build book a kid can follow, CALI-80 (#48) record the test, predicted against measured. Knock-down
  joinery stays with #9. Next free id: CALI-81.
- Tests: `test_answers.py` (the declarations are read once until the script changes), `test_cutplan.py` (a holed
  panel's triangles: the panel less the hole, facing out, eight boundary edges; the stool's left wall with a 2 in
  hole cut on its sheet), `test_promote.py` (18.98 holds a 3/4 in wall rule, 15.88 doesn't; only measured sizes
  get the allowance; a drafted rule says so), the old exact-text expectations updated. **Full suite: 515 passed**
  (with unfold-to-sheets at `8fc66c9`).
- Commits: `916745e` (#44), `f3ccee0` (the pin), `2db111e` (#45), `7622e00` (#28). PR #49.

### 2026-10-30 · CALI-59 (#8) · First run: one sentence in, four answers out
- **Theo:** "let's go #8". Spec step 5: first run lands on the four questions.
- **The first build (`firstrun.py`):** a new design used to stop after its questions at "Tell me which part to
  build first"; the stool then took six messages and a couple of clicks before its cards said anything. Now
  **Build it** on the questions (blanks take the grey suggestion, marked assumed) runs one job, said step by step:
  what it's held to (`goals.update`), the part (the whole sentence as one part, named for what it is; CALI-35
  will plan several), its description rewritten from the script, its strength check at the safety its checks
  ask for, its patterns, and the scorecard, so no check reads "not checked yet". The reply is the four answers,
  a line each, verdicts first. `POST /api/designs/{slug}/clarify` takes `build: true` (the page sends it; the
  default stays false), `POST /api/designs/{slug}/build` starts it for an answered design, and `design_state`
  says `building` so a reloaded page follows the job again. A design that's one part answers *What do I buy?*
  and *How do I make it?* with that part's list and patterns.
- **Live:** "A step stool so my 6-year-old can reach the bathroom sink, from 3/4 in plywood. It has to hold me
  too, 200 lb." → named *Step stool* (`short_name`: what it is, not the sentence cut at 60 characters), four
  questions left blank, **Build it** → 2½ minutes → holds Dad 8.07x, 1 sheet, 22 screws, about $39, 10.9 lb,
  19 pages of patterns, every check scored.
- **Samples (`samples.py`, `caliper/samples/`):** the stool and the camper as they are, with the newest run of
  each study per part (10 MB: the stool's strength heat map and patterns, the camper's drag stations); build
  packages left out. Opening one copies it into your designs (`step-stool`, `step-stool-2`…).
  `caliper sample save <name> --slug <design>` remakes one; home folders are written `~`. Their descriptions were
  brought up to date (the stool's still said "two-step") and their names shortened (*Step stool*, *Camper shell*).
- **What the numbers promise (`answers.PROMISE`):** under any strength or frame verdict, and in the build book.
  A prediction from the loads and textbook strengths, not a certificate; test it gently first.
- **Errors you choose to report (`errors.py`):** failed jobs, crashed requests (a 500 now carries an `error_id`)
  and errors on the page are kept in `~/.caliper/errors.jsonl` (or `$CALIPER_ERRORS`), the newest 50, home folder
  as `~`. **Report it…** shows the whole report (what broke, where, Caliper/macOS/Python versions, nothing of the
  design) and opens it as a new GitHub issue in the browser for the person to submit. Nothing is sent on its own;
  there's no server to send it to, and none is needed.
- **For a kid:** 🎤 beside both boxes uses the browser's speech recognition where it has one, else says how to
  start the Mac's dictation (which types into any box). **Say it simpler** under the last reply. With a key, a
  question is answered by Claude in plain words from what's measured (`chat.explain`: the four cards, the
  strength check and its notes, the last of the conversation); offline, the facts as before. Asking for it in
  plain words is always a question, never a change, even with a part selected (`_EXPLAIN`).
- **Filed CALI-75 (#42):** Theo showed it to a structural engineer friend, whose one concern was whether the FEA
  is accurate and the safety factor appropriate. #42 covers it: benchmarks with known answers at the voxel sizes
  we use, the material values' sources, a safety factor per kind of design with its basis, joints, a sandbag test
  of the real stool, and a range where the model is rough. Until then the cards say it's a prediction. Next free
  id: CALI-76.
- Tests: `test_firstrun.py` (one sentence in, four answers out: each step in order, its strength check at its
  checks' safety, its patterns, the reply; a failed build adds nothing; no strength check without whittle; through
  the API: answering builds it and a second build is refused; plain-words routing and the explain prompt),
  `test_samples.py`, `test_errors.py`; `test_answers.py` updated for a one-part design; the build book's title is
  the design's short name now. **Full suite: 509 passed** (in two runs: up to `test_release.py`, then from it).
- Commit: `73f6499`, PR into `main` (the seven-PR stack #25 → #41 merged into `main` first, in order).

### 2026-10-30 · CALI-73 (#39), CALI-74 (#40) · Lighter until the safety runs out; the four questions, steps 2–4
- **Theo:** "it seems that we've hit an artificial limit… still 3.1X safe even though we removed 3.3 pounds,
  shouldn't we take this chart down as far as I can go until the safety factor runs out?" Right: the study only
  took the walls (to one window each inside the 1.5 in glued rim), and the 3.1x is the *top's* plate check, which
  it wasn't allowed to touch.
- **Lighten, three phases (`lighten.py`):** the walls as before; then round 1 1/2 in hole-saw holes in the panel
  stood on, one at a time, quietest first; then thinner sheet as estimates (from the lightest step with the top
  solid: the plate check at that thickness, the walls' FEA scaled), adopted through the chat. It stops at the
  first step that doesn't hold (shown red). Stool: walls to 49% (3.27 lb, 3.11x) → 1–4 holes near the top's
  corners (3.29–3.37 lb, 3.09–2.98x) → a 5th, nearer the foot: **1.69x, fails** → in 5/8 in: **4.15 lb lighter,
  2.16x (estimate)** → 1/2 in: 1.38x, fails. The top works nearly everywhere; its holes save 0.02 lb each.
- **How a holed top is judged:** the plate formula ignores holes. Tried and dropped: the FEA's maximum (one corner
  hole: 3.1 → 1.8x, the stair-stepped edge of an 8-voxel circle) and its 99th percentile (still 3.1 → 2.4x). Kept:
  the rest of the panel by the FEA with a ring round each hole left out, and each hole's edge by K_t = 2 (a round
  hole in a plate in bending, Peterson) times the stress the solid panel had there; both scaled by how far the
  FEA read low against the plate check on the solid panel, recalibrated after each walls step (the top's holes go
  into the windowed part). **A bug the tests caught:** after adopting top holes, the strength check judged the top
  by the plate formula again — 3.1x for a top the study put at 2.1x. Now `judge_holed()` does it the calibrated way
  for any top that has holes (solving once with them filled, cached). The study's number and the rebuilt part's
  can still differ (stool, step 8: 2.98x here, 2.38x rebuilt — the hole edges fall differently on the grid), so
  cutting a step in reruns the strength check, and the panel says that's the number to go by.
- **Step 2:** *Will it work?* lists the design's checks (`scorecard.yaml`): a verdict from what's measured now
  (`answers.measured()`: strength runs on current versions, weight, cost, what the shop can't make, print hours),
  else the last scorecard (said so when a part has changed since), else what it needs; proposals to keep or drop.
  A design with requirements and no checks gets them written once in the background — the stool now has
  "holds Dad (200 lb), 2 times over" (assumed: the 2x is Caliper's) and reads "✓ … 3.11x"; the cargo box's nine
  hand-written checks read from its scorecard (✓ tongue 141.3 lb … ✓ floor 3.3×). The design's *What do I buy?*
  reads the measured weight and cost. `JobRunner.busy()` keeps the backfill from queueing twice.
- **Step 3:** *How do I make it?* has its own buttons: Print full size, Measure and mark, Project; Open the build
  book. **Step 4:** clicking a card's title drives the viewport: *Will it work?* the stress, *What do I buy?* and
  *How do I make it?* the pieces as built, *What is it?* the part.
- Tests: `test_lighten.py` (it goes down until it runs out: walls before the top, the top judged by the plate check
  solid and the calibrated FEA holed, estimates never adopted as they stand, hole-saw holes round; adopting and
  rechecking agree within 15%), `test_answers.py` (+1: what it's held to — not checked yet, ✓, ✗, proposed; a lone
  part answers for the design). **Full suite: 497 passed.**
- Commit: `7b8b097`, PR into #37's branch.

### 2026-10-30 · CALI-72 (#38) · The four questions, step 1: four cards, one line each, the numbers underneath
- Step 1 of `specs/caliper-four-questions-spec.md`. **`answers.py`** writes each card's lines on the server
  from what's already measured (no card runs a study to draw itself): *What is it?* (the description's first
  sentence, size, what it's cut from), *Will it work?* (each strength case as "Holds an adult stepping up, 3.1
  times over", "older version: check again", frames, rules; the scorecard for the whole design), *What do I
  buy?* (the shopping list in a line with its cost, the weight: "easy for a kid to carry" under 10 lb), *How
  do I make it?* (by tool from your shop, printed parts with hours, what your shop can't make grouped by why,
  patterns ready). A card with nothing yet says what to tell Caliper. Endpoint `/api/designs/{slug}/answers`.
- **The panel** is four cards, coloured by their worst line; "▸ the numbers" under each holds today's panels
  for that question (part: Size/Rules/History/Advanced; Will it hold?/frame/drag; Built from; Made in your
  shop/patterns/cut plan. Design: prompt/requirements/parts; scorecard/checks; weight & balance; build
  package), nothing removed, and stays open once opened (localStorage). A line from a study is a link to it;
  the Studies page opens the card a study lives in. Answers fill in place, so a half-filled form survives.
- **Glue and screws** join the shopping list (`fasteners.py`): joints found from the pieces (an edge against
  another's face or edge, each pair once), #8 screws a screw every 6 in (at least 2 a joint, ~1.6× the
  thickness long), glue ~1/2 ml an inch. The stool: 8 joints, 85 in, 18 × #8 × 1 1/4 in screws and an 8 oz
  bottle. In Built from, the scorecard's cost and the release's shopping list.
- Live, the stool's cards: "A two-step stool made from 3/4 in plywood…" (its description is stale until the
  next revision, #29's fix) · "16 × 10 in, 9 in tall, from 3/4 in softwood plywood" · ✓ "Holds 200 lb adult
  stepping up, 3.1 times over." · "1 sheet of 3/4 in softwood plywood, 18 screws and wood glue, exterior paint:
  about $39." · "It weighs 8.9 lb, easy for a kid to carry." · ✓ "With your jigsaw: 5 pieces." · "Patterns
  ready: 15 pages…". The cargo box and its frame read right too (the frame: "Your shop can't make shank,
  riser, spine and 4 more: steel tube…" until a welder and a saw are in the shop).
- Tests: `test_answers.py` (4: a five-panel box has 8 joints and its screws and glue; the four cards read top
  line first with no internal names; a strength check becomes a verdict and an older one says so; the design
  card says what isn't done). **Full suite: 496 passed.**
- Commit: `99ca894` (with the rest of CALI-48), PR #37.

### 2026-10-30 · CALI-48 (#4), the rest · Your shop: what makes each piece, and printed parts fitted to the printer
- **Theo:** "let's finish #4 and then step 1 of spec".
- **`shop.py`:** your shop as data, saved once (`~/.caliper/shop.yaml`, or `$CALIPER_SHOP`) and used by every
  design: hand tools from a catalogue (jigsaw, drill, circular saw, hot wire, knife, chop saw, hacksaw,
  welder, angle grinder…) and machines (CNC router with its bed, plasma table with its bed and thickest
  plate, 3D printer with its volume and materials). Nothing saved means a hand-tool shop: jigsaw, drill,
  circular saw. `route()` sends each piece to what makes it: the router if it fits the bed, a jigsaw (up to
  1 1/2 in, curves and holes, with a starter hole), a circular saw (straight, no holes), a hot wire or knife
  for foam, the plasma table within its plate thickness, a chop saw and a welder for tube, the printer for a
  printed part — or says what's missing ("thicker than your plasma table cuts: a fab shop can cut it").
  Foam's fold limit was already enforced: the cut plan makes any fold sharper than `fold_deg` a cut.
- **Printed parts:** a part can declare `{"kind": "printed", "material": "petg"}`; it's weighed from its solid
  (1.2 mm walls + 20% infill) and costed by the kilo (PLA, PETG in the materials table). **`printing.py`**
  fits it to the printer: turned if that's enough, else split across its longest side with three 3 mm pin
  holes, 10 mm deep each side, across every cut (a 400 mm bar on a 256 mm bed: two watertight halves). Time
  and filament come from **PrusaSlicer's command line** where it's installed (0.2 s a piece: 6.6 h, 170 g,
  $3.73 for each half of that bar in PETG), else walls + infill at rough speeds, marked rough.
- **`making.py`:** per part, every piece routed and printed parts fitted and costed. The part panel's *Made in
  your shop* says it in a line per tool ("jigsaw: left side panel, …"), printed parts with hours, grams and
  dollars, and anything your shop can't make in red. A **Shop** page edits the shop. The scorecard checks
  "your shop can make every piece" and reports print hours and filament; the build package files printed
  pieces under `printer/<part>/` and the book gets a *Made in your shop* page.
- Tests run against an empty shop and no slicer (`conftest.py`), whatever this machine has. `test_shop.py`
  (6: the default shop and saving yours; routing for hand tools and for machines, including too-big and
  too-thick; the stool by jigsaw; a printed bar split and pinned, weighed as printed; split pieces fit and
  lose only the pin holes; the scorecard's shop check). `test_scorecard.py` counts the new check.
- Commit: `99ca894` (with CALI-72), PR #37.

### 2026-10-30 · CALI-48 (#4), first slice · Patterns for hand tools: measure and mark, print and tape, project and trace
- **Theo:** "a cut plan with a jig saw is important. CNC is great, but most people operate with hand tools.
  We need plans that can be laid out by ruler and pencil, or maybe projected with a projector and traced or
  printed or something like that."
- **`patterns.py`:** every flat sheet piece of a part (holes and all), in its own plane with its longest edge
  along the bottom and its corner at (0, 0), three ways:
  - **Measure and mark** (`measure-and-mark.pdf`): a landscape page per piece on a 1 in grid, numbered from
    the bottom-left corner, overall dimension lines, the corners of anything that isn't a plain rectangle,
    and each hole's position and size from the two square edges ("H1: 1 1/2 in from the left, 1 1/2 in up;
    11 7/16 in wide, 6 in tall… drill a 3/8 in hole inside the line to start the jigsaw").
  - **Print and tape** (`print-full-size.pdf`): full size on letter pages, portrait or landscape (whichever is
    fewer), 1/2 in overlaps shaded grey, the 1 in grid to line pages up, a label on each ("page A2 (2 of 2) ·
    overlaps …"), a 3 in ruler in every top margin to check it printed at 100%, and a map page per piece.
  - **Project and trace** (`project-<piece>.svg`): full size in real inches, white on black, with a 4 in
    calibration square to zoom the projector to.
  Pages are Pillow rasters at 150 dpi saved as PDF with their resolution, so they print at true size with no
  PDF library (every page is 612 × 792 pt). A 1/4 in border pushed a 14 1/2 in panel onto a third, nearly
  empty page; it's 1/10 in now: the stool is 10 printed pages, two a piece.
- **In the app:** *Patterns for hand tools* comes before the CNC cut plan under *Built from*, with links and
  thumbnails; it's on the Studies page. **The build package** gets `hand/<part>/` with all three.
- Live on the stool (v3): 5 pieces, 15 pages with the maps.
- **Not yet in #4:** the shop itself (machines and stock as a design input), the printer, routing by machine.
- Tests: `test_patterns.py` (3: pieces lie flat, long edge down, holes in place; every printed page is
  8.5 × 11 in and the PDFs, SVG and history are right; nothing flat, no patterns) and `hand/` in the release.
  **Full suite (over #2 and #4): 486 passed.**
- Commit: `92248f0`, PR #37 (stacked on #36).

### 2026-10-30 · CALI-55 (#2) · What the design is held to, written from the conversation
- **`goals.py`:** after the clarify round (in the background, off the request) and after any chat turn that
  sounds like a requirement (an obligation, a load, or a number with a unit), Claude rewrites the design's
  `scorecard.yaml` checks from its goal, requirements (answered or assumed), parts, the checks it has, a
  catalogue of metrics, and what was just said. Each check is **stated** (the person said it and the limit;
  their words kept), **assumed** (an assumed answer, or a number Caliper picked — the 2x behind "hold me"),
  or **proposed** (nobody said it, the design needs it; it doesn't bind until kept). A kept check stays kept;
  a dropped proposal is never offered again. Offline, "hold … 200 lb" still becomes a strength check. A
  goals file written by hand (the camper's) is never rewritten (`written_by: caliper` marks ours).
- **Live tuning (scratch stool):** the first prompt doubled the strength requirement (safety factor *and* a
  "stated" breaking load) and put "9 in off the floor" on the breaking-load metric. Rules now: one check per
  need, only what a listed metric measures, any number Caliper picked makes it assumed, short labels in the
  person's words; and in code, one check per metric and no unstated breaking load beside a safety factor.
  Result: "holds Dad (200 lb), 2 times over" (assumed), proposals "under $50" and "cuts fit on 1 sheet";
  then "keep the whole thing under $40 and light enough for him to carry" → "under $40" (stated) and "light
  enough for a 6-year-old to carry" (≤ 10 lb, assumed).
- **The scorecard** gains `strength.safety`, `strength.<part>.safety` and `strength.breaks_lb` from each part's
  strength check on its current version (run if missing); proposed checks show as ◇ and don't count. The
  panel shows where each check came from (*you said*, *assumed*, *kept*, *proposed* with **Keep**/**Drop**),
  before the first card too; the chat reply says what went on the scorecard and what it would also check.
- Tests: `test_goals.py` (5: offline strength check; a hand-written file left alone; Claude's stated,
  assumed and proposed checks, an unknown metric dropped, keep and drop and both standing after a redraft;
  a proposed check shown but not counted, the strength metric from the part's run; a requirement-ish turn
  updates the checks and a question doesn't). `test_scorecard.py`'s summary gains `proposed`.
- Commit: `e94ea70`, PR #36 (stacked on #35).

### 2026-10-30 · CALI-71 (#32) · Lighten the walls where the wood isn't working, in cuts a jigsaw can make
- **Theo:** "proceed to 32, 2 and 4", after the interface spec (`specs/caliper-four-questions-spec.md`, PR #34).
- **`lighten.py`:** the panels the loads pass *through* (not the one a load lands on face-on, which stays solid
  and keeps its plate check) are rastered at the voxel size, each cell a column through the plywood. Step by
  step (25/50/75/100% of each panel's inside), the quietest columns of what's left, by the strength check's
  own FEA across every load, come out; the result is cleaned into holes a jigsaw can cut (1.5 in solid rim
  where it's glued and screwed, no hole or web under 1.5 in, smoothed both ways and rounded to 1/2 in,
  clipped inside the rim), the voxels under those exact holes are removed, and the part is re-analysed. It
  stops at the first station that doesn't hold. `load_study` is split into `prepare()` + `check_load()` so
  both studies judge the same way.
- **`HOLES` (holes.py):** adopting a station writes the holes into the script as data; the sandbox cuts them
  after `build()` and gives them to the named pieces, so the take-off (area, weight, paint), the consistency
  check (samples skip holes, volume subtracts them) and later revisions all see them. The reference documents
  it; the designer is told to keep it. The CNC cut plan says the holes aren't on its sheets yet.
- **Live, on the stool (v3, study only — not adopted):** 49 s, 4 walls: 11% (2 holes, 0.7 lb) → 14% → 31% →
  **49% of the walls, 4 rounded windows, 3.3 lb lighter, still 3.1x** (the top's plate check governs
  throughout; the walls' FEA safety goes 10.9 → 4.9). On a scratch copy, adopting it: 6.9 L → 4.3 L of
  plywood, 8.9 → 5.5 lb, watertight, all four consistency checks pass.
- **The UI:** *Make it lighter* under *Will it hold?* — run it, click a step to see it in place, **Cut these
  holes**. The thickness table's **Use** asks the designer for that plywood, through the chat.
- **The build book** gets a *Will it hold?* page: each load, its safety, where it should break, and a blank
  for where it did (#10's sandbag test).
- Tests: `test_lighten.py` (4: holes cut, weighed and consistent; merge; the walls lighten, the top doesn't,
  every hole keeps its rim; adopting cuts them and a second study starts from them) and the book's
  breaking load in `test_release.py`. **Full suite: 478 passed.**
- Commit: `e431f44`, PR #35 (stacked on #33).

### 2026-10-30 · CALI-67 (#27), CALI-69 (#29) · Panels that fit the design, and a description that keeps up
- **Theo,** walking through the strength check: the rough edges I'd listed were his feedback ("the whole
  interface is a bit complicated… how can even my 6 year old make something while still being useful for a
  real mechanical engineer"), then "proceed with #27 and #29".
- **#27, one rule for drag:** `studies.in_air()` reads the design's prompt, requirements and part
  descriptions for a vehicle, a road speed or wind (car, trailer, hitch, cargo box, mph, wind…; not "towel"
  or "window"); a reference part (the car) or existing drag studies also count. Without it, **Shape it for
  drag** and **whittle carving** are gone from the part's panel, and the Studies menu says why ("nothing in
  the design says it moves through air … say so and the drag studies appear"). The design's **Weight &
  balance** shows the hitch, its moment, the payload box and the lb·in columns only when a part declares
  where it's held; otherwise it's the weight and the red dot. The balance no longer adds "No part declares
  supports() — no hitch point". New-design placeholder: a step stool, not a cargo box on a hitch.
  Stool: Size, Rules, Will it hold?, Built from, History. Cargo box: unchanged (hitch 2,103 lb·in, drag).
- **The strength view's rough edges:** **Will it hold?** moves above **Built from** (it was under the cut
  plan). The colours are brighter (blue to red, not navy to fog) and the centre-of-gravity dot steps aside
  while they show. The bar says which number is which: the colours are whittle's FEA (0–2.8 MPa on the
  stool) and the verdict is the plate check's (4.8 MPa, grain the wrong way), with the breaking load.
- **#29:** after every revision, `chat.redescribe()` asks Claude for the part's one-line description from the
  old one, the change and the new script (unchanged if still true, nothing the script no longer builds);
  offline, the old one with "(revised: …)" — the latest change only. Live, on a copy of the stool: "A
  two-step stool … two treads, … a back brace, and a middle riser" became "A single-step stool … two side
  panels, a front panel, a back panel, and a top tread, standing 10 in tall" after "make it 10 in tall".
- Tests: `test_studies.py` (+1: the stool isn't in air even with a towel rack by the window; a cargo box,
  a wind turbine, something behind a car and a design with drag runs are), `test_chat.py` (+2: Claude's
  new description lands and the conversation reads it; offline it says what changed, latest only).
  **Full suite: 473 passed.**
- Commits: `cf163fa` (#29), `e29472c` (#27), on PR #33 (stacked on #30).

### 2026-10-29 · CALI-54 (#1), CALI-70 (#31) · Will it hold? And one page for every study
- **Theo:** "please launch and I'll take a look at the results! And I think we need a page in the app, or a
  menu to access all of these studies". Second slice of #1: a study for a part the designer writes.
- **`loads()` (and `held()`)** join the part-script reference: what pushes, how hard (`lb`/`kg`/`force`), a
  `factor` (2 for someone stepping on), and the box it pushes on; held at the floor unless it says. The
  designer is told to write it when the requirements name a load. A new check, `loads_land`, fails a round
  whose load box doesn't touch the part ("… 40 mm from the part — put its box on the face it pushes on").
- **`load_study.py`:** whittle's `LoadStudy` in-process, in the material `construction()` names (Caliper's
  own E and strength, so the BOM and the FEA agree), at 4 voxels through the thinnest piece (capped at 150k
  voxels). Per load: the FEA's peak *beside* the load and the floor (whittle's robust 99th percentile leaves
  the hardest-worked spots out: 1.9 MPa on the stool, against 2.8 where the top meets the front), how far
  it gives, where it works hardest, a stress picture on the part's own surface. And a **plate check** for a
  sheet pushed face-on that rests on other pieces all round (Roark Table 11.4, simply supported, the load at
  the middle; checked against Timoshenko and by hand), said both ways for plywood's grain, with every
  thickness sold. The verdict takes the worse; "breaks at" is load × factor × safety.
- **Why both:** measured on the stool's top at three voxel sizes, the FEA's numbers wander (deflection
  0.14/0.15/0.10 mm, peak 3.9/2.7/2.3 MPa) inside the plate formulas' range (2.8 clamped to 4.8 MPa simply
  supported). The fused voxel joints read stiffer than glued-and-screwed; the plate check is the safe side.
- **Live, through the chat only:** on the stool (v2), "It has to hold me too: 200 lb, stepping up onto the
  top." The router first called that an answer (it "changes no geometry") and replied with a summary; it now
  routes a requirement on a part to a refine. → v3 in 1 round: `loads()` exactly as the reference shows it
  (200 lb × 2, a 4 in foot in the middle), shape unchanged, every check passing. **Check it holds** (15 s,
  65,040 voxels of 4.8 mm): **holds, 3.1x** — the plate check on the top tread (14.5 × 8.5 in, held all
  round: 4.8 MPa → 6.2x with the face grain across the 8.5 in span, 3.1x the other way, sags 0.26 mm); the
  FEA puts the hardest-worked spot in the front panel where the top meets it (2.8 MPa, 10.9x). The thinnest
  ply that holds: 5/8 in (2.2x); 1/2 in doesn't (1.4x). The chat's reply now says the requirement went into
  `loads()` instead of "I can't make it a rule".
- **The Studies page (CALI-70, #31):** a header button; per part, every study and why it can't run yet
  (reference parts get none); every run newest first with the version it ran on (from the part's history
  when the run didn't record one), "changed since", and its one-line result; **Open** goes to the run in its
  panel, a strength check on its stress picture. `studies.py` builds it from the runs `design_state` loads.
- **Filed:** CALI-71 (#32), lightening a sheet part's panels with through-cuts a sheet can take (whittle's
  plate study per panel, checked in 3D), which #10's stool needs.
- Tests: `test_load_study.py` (6: the plate formula against Timoshenko and the hand number; loads parsing;
  a load in thin air fails the round; the stool with an overhanging top gets the FEA and no plate check; a
  box stool gets the plate check, grain both ways, thicknesses, breaking load; no loads, no study),
  `test_studies.py` (4), and the strength reply in `test_promote.py`. **Full suite: 470 passed.**
- Commits: `4e7d2a1` (strength), `1e17020` (studies page), `b7a2ef5` (docs), on PR #30.

### 2026-10-29 · CALI-54 (#1) · The designer writes what a part is built from, and it's checked
- **Theo:** "go ahead and start on #1 with the stool". First slice: from a plain request, the designer writes
  `BUILD` + `construction()` (and `members()`/`supports()` for a frame) beside `build()`, and every build is
  checked against them.
- **One reference:** `src/caliper/part_scripts.md` documents every declaration (PARAMS/build, BUILD and
  construction, members/supports/jacks/GUSSETS/LAYOUTS, keeps, RANGES, shell/roof). The generator's system
  prompt carries it word for word (`authoring.system_prompt()`), plus a materials table generated from
  `materials.py`, so the prompt can't offer a material Caliper doesn't know. CONTRIBUTING points at it.
  `chat.TUNABLE` shrinks to a reminder to keep the declarations with the shape.
- **The check (`consistency.py`):** the sandbox runner now returns `construction()`/`members()` from the same
  run that built the part, and `authoring.improve` adds four measurements to every round:
  `construction_reads` (they run, with known materials), `construction_inside` (each piece's middle is in
  the solid; a tube's centreline within half its width, so hollow tubes pass), `construction_covers`
  (≥ 98% of the solid's surface lies on some piece, each sheet's thickness going one way, into the solid)
  and `construction_volume` (≤ 1.25x the solid). A failure fails the round with where it is, e.g.
  "9% of the solid's surface isn't on any piece: around (201, 250, 106), within … y 235..273".
- **Live, in the app (default chat, no script by hand):** "A step stool so my 6-year-old can reach the
  bathroom sink. Made from 3/4 in plywood, glued and screwed. It has to hold me too (200 lb)." → 4
  clarify questions (suggestions taken) → "build the stool" → v1 in 2 rounds, with `construction()` (six
  panels) written unprompted. v1 had a riser two sheets thick in `build()` and one in `construction()`; the
  first version of the check (two-sided thickness, 95%) let it through at 96.5%; the one-sided check fails
  it at 91.3%, exactly there. → "make the stool a single platform like we said…" → v2 in 1 round: five
  panels, inside 100%, covers 100%, volume 1.00. Built from: 8.9 lb, one 4x8 sheet of 3/4 ply + paint.
  Cut plan: 1 sheet, 12% used, all five panels nested (DXF, SVG, PDF).
- **The camper's hand-written parts pass the check as they are:** cargo_box (an envelope: covers 99.9%,
  volume 0.11) and frame (covers 100%, volume 0.94).
- **Router fix:** v1 was "a two-step stool" because the LLM router writes a new part's intent from the goal
  alone; it now sees the requirements and is told not to contradict them.
- **Not yet:** a study for a part the designer writes. Caliper drives only whittle's drag mode; "does it
  hold Dad" needs its load (FEA) mode with plywood, the person on the top and the floor as supports. Also
  found live, filed: the inspector offers a hitch rating and a drag study for a bathroom stool (CALI-67,
  #27); a promoted test reads a 19.05 mm sheet measured at 18.98 as a miss (CALI-68, #28); the part's
  description stays "two-step" after it's made single (CALI-69, #29).
- Tests: `test_consistency.py` (10: a stool that matches; a panel left elsewhere, one left out, one built
  thicker than its sheet, a sheet listed twice as thick; a declaration that raises or names balsa; nothing
  declared; a hollow tube frame; a mismatch failing a round with the fix in the feedback; the prompt
  carrying the reference and every material) + the router test.

### 2026-10-29 · CALI-60 (#5) · Install for a stranger: README, CONTRIBUTING, `make tools`
- **README** rewritten for someone who isn't us: what it does (design, test, plan the build, price,
  release), honest status (#1 is the biggest gap), install with micromamba, run, the CLI, how it fits
  together, and a plain warning that Caliper runs the Python Claude writes (a worker process with a timeout,
  not a security sandbox). The Theo-machine notes (sandbox, `/opt/anaconda3`) are gone from it.
- **CONTRIBUTING.md**: setup, `make test` / `make review`, the `?v=N` and restart gotchas, issues and
  commit conventions, definition of done, the optional tools, part-script declarations (pointing at #1),
  generated code and private vulnerability reports, contributions under Apache-2.0.
- **No local paths:** `cutplan.unfold_dir()` = `$CALIPER_UNFOLD_DIR`, else `vendor/unfold-to-sheets`, else a
  checkout beside the repo (test added). The whittle hint says `make tools`. "Theo's" dropped from the
  docstrings.
- **`make tools`:** whittle and unfold-to-sheets at pinned commits (`WHITTLE_REF` 5363df5, `UNFOLD_REF`
  54e1af4); leaves an editable whittle and a symlinked `vendor/` alone (checked here; and from a scratch
  folder it clones, checks out the pin, and re-runs cleanly). CI uses it, so the pins are proven there.
- `environment.yml` gains `httpx` (the server tests need it; `requirements-pip.txt` had it). CI actions
  moved to Node 24 majors (checkout v5, setup-node v5, setup-micromamba v3).
- Tests: cut-plan + release 15 passed here; PR #25's first CI run before this commit: 447 passed, 0 skipped.

### 2026-10-29 · CALI-60 (#5) · Open source, and the tracker moves to GitHub
- **Theo:** "let's move our issues onto GH … let's move this into open source, and start the work to get this
  into fighting shape". He picked Apache-2.0 for all three repos, and a push + PR for the M4–M6 branch.
- **Issues:** every open card, plus the V1 gaps found while planning the showcase video, filed as
  greentheo/caliper #1–#24 with milestones (V1, M6, M5) and labels (P0–P2, area, showcase, parked, blocked).
  `BOARD.md` and `TASKS.md` are frozen as history; the board maps each open card to its issue. The duplicate
  CALI-12 line is gone.
- **New V1 cards:** CALI-54 the designer writes the study inputs (`members()`, `construction()`, `shell()`…)
  from the chat — today it only keeps them, so a design started in chat gets no study, BOM or cut plan;
  CALI-55 goals from the conversation; CALI-57 the Mac app; CALI-58 App Store spike; CALI-59 first run;
  CALI-60 open-source readiness; CALI-61–63 showcase builds (the stool, a Savonius turbine, the camper
  redone through chat); CALI-64 end of life (Theo's furniture-that-composts vision); CALI-65 the video.
  CALI-35 (decomposition) and CALI-48 (the shop) moved into V1: the turbine needs both.
- **Licence:** Apache-2.0 (`LICENSE`, `NOTICE`, `license = "Apache-2.0"` in pyproject, setuptools ≥ 77).
  whittle was already MIT, so it's left as is; unfold-to-sheets gets Apache-2.0 in its own PR.
- **CI:** `.github/workflows/tests.yml` runs the suite on every PR and on main: micromamba CadQuery,
  pip for the rest, whittle from git, unfold-to-sheets cloned for the cut-plan tests, no PDF.
- Audit before pushing: no secrets in any branch's history (only `sk-ant-...` placeholders).

### 2026-10-28 · CALI-51 · The build package
- **Theo:** "build it! and relaunch the server, I need to take some screenshots to show a friend".
- **`release.py`:** `make()` → `releases/<NNN>/` — cut plans and scorecard brought current, then the build
  book (HTML; PDF via headless Chrome, own temp profile), `plasma/`, `router/`, `assembly/` (a PNG per step),
  `cutlist.txt`, `shopping.txt/.csv`, `scorecard.json`, `source/`, zip. Assembly order from the layers
  `construction._layer` already sorts pieces into, parts bottom-up, then skin, mount, finish.
- **Drawings:** first as painter's-sorted SVG — big faces covered what's in front of them, and coplanar
  patches z-fought even after subdividing; now a small numpy depth-buffer rasteriser (fan triangles, plates
  even-odd with plane depth, outlines depth-tested, 2× supersampled) writing PNG with zlib only.
- **Bug found — mirrored panels inside out:** the right-hand bands are the left's mirror, so their winding
  (and normals) flipped; unfold-to-sheets read every right-side seam as 180° − its angle (bevel 50–71° vs
  19–40° on the left) and couldn't tell inside from outside (128 mountain / 128 valley). `panels_obj` now
  winds every face away from the part's middle: 233 mountain / 23 valley, bevels symmetric. Same 4 XPS
  sheets at 59%. Cut plan re-run for cargo_box v14.
- **Bug found — the server crash:** four concurrent `GET /api/designs/<slug>` killed it (SIGABRT; SIGSEGV
  when two tabs loaded together) — OCCT from FastAPI's thread pool. `occt.OCCT` (an RLock) now wraps
  `DesignStore.evaluate`, `part_geometry`, the sandbox's STEP import and promote's part load. 12 concurrent
  design loads + STL fetches: all 200, server up.
- **Camper release 001:** frame v26, cargo_box v14; ready to cut (11/11); 11 steps; 5 sheets; ~$566 to buy
  (rounded up to what's sold; the scorecard's $451 is what's used). Shopping: 6 ft 2x2x1/8, 14 ft 1x1x1/16,
  a 19 × 18 in piece of 1/8 plate, 1 ply + 4 XPS, 5 1x2 + 3 2x2, 8 yd cloth, ½ gal epoxy, 3 qt paint, two
  jacks rated 500 lb+.
- Tests: `test_release.py` (8), `test_cutplan.py` +1. Full suite green (447 passed).
- Commit: `3170a12`

### 2026-10-28 · CALI-53 · Parked on the jacks
- **Theo:** proceed (200 lb + 50 lb of gear, 150 lb a knee, jacks under the X's back corners).
- **Frame v25:** `jacks(params)` at the X's back corners (push only). `parked.py`: lying (×1.5) + kneeling
  at 9 spots; jacks that would pull lift off and the case re-solves; floor check by a plywood strip over the
  widest clear gap (2 × the floor's reach to a tube or wall = 22.6 in).
- **Results:** frame worst 2.24× (X front arm, kneeling at a front corner — the far jack lifts); walls ≥ 2.45×;
  jacks ≤ 288 lb each (a pair rated 500 lb+ is plenty); floor 3.3× on the mattress, 1.84× bare ⅜ ply (0.5 in
  sag); **hitch up to 356 lb** kneeling at the front middle — over the 350 rating with the bouncy 150 lb knees;
  260 lb with 100 lb knees; 285 lb with front jacks too. Theo: no front jacks; the 350 rating is
  conservative (likely 2x) — check at 420 lb (+20%), driving and parked. Scorecard **11/11 pass**.
- Tests: `test_parked.py` (2). Full suite green.
- Commit: `e302a20`

### 2026-10-28 · CALI-52 (part 2) · Three beams, a glass patch, and the skeleton on screen
- **Theo:** the local patch — yes; jacks under the corners of the X; three beams (2.7×); "let me know when I
  can see the skeleton (maybe we can toggle off each object/layer?)".
- **Box v14:** `roof_beams` 3; `corner_patch: glass_patch` — a new covering (one more layer of 6 oz + epoxy,
  no paint, 0.41 kg/m²) as a stand-alone `covering` item over the front panel's corners (4 in past where
  the shoulder starts, up to the corner beam's depth), and the front corner wall beams carry it as one more
  skin. Walls 3.37× → **4.98×**; +0.5 lb (½ yd of cloth). Scorecard **8/8**: 141 lb on the hitch, snow 2.7×.
- **As-built view:** `pieces3d()` + `/pieces` route; the page draws sheets (translucent, edged), sticks and
  tubes (boxes on centrelines), plates (ExtrudeGeometry on their placement basis, both cheeks); a layers
  panel toggles floor / panels / shell / patches / skeleton / tubes / gussets and a faint solid; parts
  re-fetch when their version changes. Checked in a background tab: the 1x2 frames, three beams and patches
  on the box; the X, spine, riser and the brass cheek plates on the frame.
- **Next:** the parked case on jacks under the X's back corners, with Theo inside (< 350 lb total) — the
  floor over the X under a person, the jacks' loads.
- Tests: `test_construction.py` +2. Full suite green.
- Commit: `568880b`

### 2026-10-28 · CALI-52 · The skeleton, searched under snow — and Theo's hitch call
- **Theo:** the hitch: 350 lb tongue weight (a Class III does 800); since the whole weight sits on the tongue,
  keep dynamic loads under ~3.5×; the lever-arm limit set aside — "worst case it bends the central spine,
  I may just have to test that"; 2x2x1/8 for spine, riser and tang; jacks at the back when parked, under
  350 lb with him in it. Snow: 20 lb/ft² ("1 lb/ft² per inch… a huge dump").
- **Frame v23:** 2x2x1/8 throughout — 25.8 lb of tube, 2.14× on a ×2.5 bump (yields at ~5.3× standing);
  gussets re-sized (v24): 0.69 kg / 5.9× / 90% off, 0.65 kg / 3.8× / 82% off. Flagged (scorecard note): a
  1/8 wall tang in the receiver bears ~1,300 lbf at the mouth on a bump — dents/ovaling; a 1/4 in wall or a
  sleeve for the 13 in shank is ~2 lb.
- **Skeleton (box v12):** front and back frames + roof beams as construction choices, `roof()` for the snow
  check, `snow.py` (panel/beam/rail checks) and `snow.search()` (exhaustive — 64 combinations in ~3 min).
  Lightest that holds 2×: **1x2 frames + two 2x2 beams across, no inside skin: 57.1 lb, $379, 2.01×** (box
  v13). Next up: three across, 59.2 lb, 2.7×. 2x2 frames unnecessary; an inside skin +9 lb/$117 for no gain.
- **Scorecard:** goals rewritten from Theo's words — tongue ≤ 350, frame survives 3.5× standing
  (`frame.yield_x`), walls/gussets ≥ 3.5× on a bump, snow ≥ 2×, every piece fits; the moment an objective.
  Notes on the card (the tang, fatigue). Result: 7 pass, 1 fail — walls 3.37× at the front wall's corner
  pieces (heavier box, more flexible frame); two layers of glass everywhere: +6 lb → 4.4×; a local patch
  would do it for < 1 lb (Caliper can't model a patch yet). 138.7 lb with 50 lb aboard, $439, 20% offcut.
- **Shape fingerprint** now ignores comments/layout; `shell`, `roof`, `BUILD_OPTIONS` not shape.
- Tests: `test_snow.py` (5). Full suite green.
- Commit: `787beac`

### 2026-10-28 · CALI-46 wrap + CALI-47 · 2 in riser, and the scorecard
- **Theo:** go with the 2 in riser, then start the scorecard. Skeleton: posts where the shell is flat — a box
  inside the box — plus roof beams for a mild snow load, 1x1 ribs only if needed; "is there a way to do
  some sort of evolutionary optimization here?" (yes: CALI-52, the loop's first job). On the M6 spec: gates
  are user-specified constraints, colloquial, on the optimize side, and Caliper must find the crucial ones
  (the mattress) early; budgets default 10 min, user-set; cost **and waste** as objectives (the quadfecta);
  printed camper parts as the printer test case. Spec updated (§0, §5, §6, answers).
- **2 in riser:** frame v21 riser 2x2x3/16 (faces flush with shank and spine — no spacers): 30.2 lb of tube,
  3.56× (shank). Gussets re-sized at 1/8: jog_low 0.69 kg, 6.0×, 86% off; jog_high 0.65 kg, 3.8×, 80% off;
  v22. Frame 36.0 lb; design 133.5 lb, 3,108 lb·in standing. Cut plans refreshed.
- **Scorecard (CALI-47):** `scorecard.py`, `materials.PRICES` (rough; tube $1.90/lb, plate $1.50/lb, sheets
  whole), `frame_study.analyse`, `aero.drag_now`; goals in the design's `scorecard.yaml` (written for the
  camper from Theo's answers so far: payload 50, frame ≥ 3.3, walls ≥ 3.5, gussets ≥ 3.5, hitch ≤ 2,450
  *assumed*, every piece fits; objectives drag/weight/hitch/steel/cost/waste/sheets). First card: 6 pass, 1
  fail (hitch), drag 48.4 lbf, 134 lb, $446, offcut 23%. ~11 s.
- Tests: `test_scorecard.py` (4). Full suite green.
- Commit: `9fe2542`

### 2026-10-28 · CALI-46 (part 2) · Gusset plates — whittle plate mode, into the design and the cut plan
- **whittle-agent shipped plate mode** (whittle `plate-mode`, uncommitted): `frame.gusset(node, m1, m2,
  thickness, plates)` → `PlateStudy.sweep()` → stations whose `.design` is a `Cut` (outline + holes, `.dxf()`
  R12 mm with `$INSUNITS 4`, `.svg()`), metrics (mass, safety, stress, sag, holes) and — asked for — how much
  of the corner weld's moment the plates take (`plate_share`, `weld_moment_nmm`, a sentence in `.note`).
  Reach now runs the member's full length; notes say when to cut one plate over both corners, and the ¼ in
  spacer the 2 / 2.5 in faces need.
- **Caliper:** `GUSSETS` in the frame script names the joints; `frame_study.gussets()` builds the frame
  carrying the design as built (walls, 50 lb), runs each joint, files every station's DXF/SVG under
  `designs/<slug>/gussets/<id>/`, picks the lightest that keeps 3.5×; `adopt_gussets()` writes `PLATES`
  (data — not shape, so drag studies still apply); the frame's `construction()` weighs them; the cut plan
  draws them via whittle's `Cut`. API `/api/designs/{slug}/gussets*`; page: *Gusset plates* under Size the
  frame. Fixed on the way: a support with `fix: "all"` was split into letters by `build_spec`.
- **Theo's frame:** 3/16 plates: 1.02 / 1.09 kg each, 5.7× / 7.3×. 1/8 plates: **0.74 kg, 6.5×, 84% off the
  riser/shank weld** and **0.71 kg, 4.3×, 82% off the riser/spine weld** — adopted (frame v20). The X's middle
  plate dropped (v18). Frame 36.2 lb (29.8 tube + 6.4 plate); design 133.7 lb, **3,109 lb·in** standing.
- Open for Theo: the ¼ in spacer (shank and spine faces sit ¼ in inside the riser's) or a 2 in riser.
- Tests: `test_frame_study.py` +1 (skips without plate mode). Full suite green.
- Commit: `6e64f16`

### 2026-10-28 · CALI-46 (part) + M6 spec · Tube end cuts, foam bevels, and the make loop
- **Theo:** proceed; and the bigger question — design, optimization and manufacture as one iterative
  cycle, his shop (CNC plasma, CNC router, small 3D printer, a big printer later) as constraints, him in the
  loop only to verify stages. Answered with a plan and wrote it up as `specs/caliper-make-loop-spec.md` (M6:
  scorecard → the shop → moves → loop runner → build package; three gates: requirements + shop, trade-offs,
  release to cut; never silent about relaxing a requirement). Board: M6 cards CALI-47…51.
- **Tube end cuts:** `cutplan.tube_cuts()` from members(): setbacks to the face butted, mitres from the
  angle, corners closed by the bigger tube. Checked by hand on Theo's frame (X arms 42.04 in centreline −
  1 in ÷ sin 63.1° = 40.92 in, mitre 26.9°).
- **Bevels:** the driver groups unfold-to-sheets' seams by the pair of pieces and reports length and the
  angle they meet at; the cut list bevels each edge at half (≥ 2°). Seen: the shoulder is nearly vertical
  with tumble 52 mm over 865 mm, so the bands are near-coplanar in the middle (0–3°) and the top band meets
  the roof at a corner — the strip-built split is mostly for the nose and tail.
- **Plate mode:** forwarded Theo's go-ahead (his words: "okay great, yes, let's do proceed") to the
  whittle-agent with the joint loads; it's building `frame.gusset(...)` on whittle `plate-mode` (its PRs #1,
  #2 — the frame-study work — are merged to whittle main). Its flag: the 2 in shank and 2.5 in riser
  faces are ¼ in apart — a cheek plate needs a spacer, or a 2 in riser.
- Fixes: score-line count counts only what's drawn; cut-plan notes only for the materials present.
- Tests: `test_cutplan.py` +1. Full suite green.
- Commit: `005321a`

### 2026-10-28 · CALI-45 · The cut plan — and the frame gets its 1 in X
- **Theo's calls:** switch to fiberglass; 5/16 shank at 3.3× is fine; fasten the box to the spine too; show
  the cut plan; look at `game-dev/unfold-to-sheets` (his tool: unfold a mesh into flattenable pieces, nest
  onto stock, score lines, DXF/SVG/PDF, seam tokens) — thinking 1 in foam folded at scored lines, spray foam
  and a rasp where it's too curvy.
- **Design:** box v10 BUILD `skin_out` fiberglass (47.5 lb). Frame v16: riser to x −4 in (under the box's
  front wall), spine to the back, shank 5/16 wall, layout *X only, spine to the back* added; `build_spec`
  now splits a wall wherever a frame joint sits under it, so the box is fixed at its front-middle and
  back-middle as well as the corners (6 fixings). Sizing with the shank held at 5/16 (min 3.3×): the walls
  carry the box to the spine and the X only steadies the corners — it drops to **1x1x1/16**. Frame v17:
  shank 13 in 2x2x5/16, riser 8 in 2.5x2.5x⅛, spine 38 in 2x2x⅛, X 4 @ 42 in 1x1x1/16 + gusset = **33.0 lb**,
  **3.57×** (shank), sag 0.31 in; weakest wall 3.6× (glass, wrinkling-limited); front-middle fixing ~110 lbf
  on a bump; the X's middle joint only 234 lb·in now (the gusset can shrink). Design: 130.5 lb with 50 lb
  aboard, **3,147 lb·in standing**. (Spine to the middle, fastened at the front only: 37.3 lb at 3.54×.)
- **unfold-to-sheets integration:** read its SPEC/README — OBJ groups are authored seams and win over its
  curvature segmentation; `resolveStock` takes objects, so Caliper passes 1 in XPS / ⅜ ply / 3/16 plate as
  stock + material objects and needs nothing changed in that repo. `unfold_driver.mjs` (node 22) imports its
  modules, runs `prepare → runScale → buildSheets → buildPackage`, writes the package and prints a JSON
  summary. It scores any fold over 0.5° (a module constant — card); the driver drops folds under the
  material's `score_min_deg` (5° for 1 in XPS) before drawing.
- **First run:** each shoulder was one piece over the doubly curved nose and tail → 5 sheets at 47%, ~330
  score lines per shoulder in a crosshatch (spread 44 mm). **Strip-built instead** (box v11, same shape and
  weight): bands front to back, one per facet of the shoulder curve → 21 pieces on **4 sheets at 59%**, every
  edge exact, 118 score lines (nose and tail; the middle bands are straight). Plywood floor 1 sheet (67%);
  frame: 2 gusset halves on a plate offcut; cut list: 2x2 posts 2 @ 14 in + 2 @ 11.8 in; tubes as above.
- **Rough edges (next):** panels are cut to the outside surface (no bevels or inside-face offsets for 1 in
  foam yet); seam tokens are per facet edge (16 along a band's edge — merging runs between the same two
  pieces would read better; that's on unfold-to-sheets' side); the posts are short now that the shoulders
  lean in — the skeleton wants placing where the shell needs it; tube end cuts (copes at the spine) not yet.
- Tests: `test_cutplan.py` (4; the unfolder ones skip where node/unfold-to-sheets aren't). Full suite green.
- Commit: `8fe590a`

### 2026-10-28 · CALI-44 · The box moves in, carries itself, and could be fiberglass
- **Theo's calls:** drag design 2; X-only frame; 50 lb aboard; count the walls' strength and stiffness;
  fiberglass as an alternative to PMF; move the box close — the trunk is reached through the fold-down rear
  seat, so the hatch needn't open ("even just a few inches clearance").
- **Applied (design revisions):** cargo_box v7 = design 2 (wall_h 176, tumble 52, shoulder 1.4, nose 400/298,
  tail 662/159/228 mm); v8 = moved to `x_front` −3 in (3 in behind the bumper; was −18); v9 = `shell()`.
  frame v14 = follows the box, layout *X only, spine to the middle*; v15 = sized (below). Assembly: rule
  `hatch_clearance` retired, `bumper_clearance` (`min_clearance(cargo_box, leaf_rear) >= 2 in`) added — passes
  at 3.0 in; part `hatch_swing` removed from the design (files kept). Requirements recorded (no hatch access;
  ~50 lb aboard).
- **Moving in is the big lever:** box CoG 25.5 in behind the receiver mouth (was 41). With 50 lb aboard the
  receiver holds **3,428 lb·in standing** (152.8 lb) — vs 7,963 with 100 lb at 18 in. The shank no longer
  dominates at this size; the X's back arms do.
- **Drag at the new spot:** whittle scores the same (215 N vs 313 N plain) at 3 in or 18 in — its shelter is
  a silhouette, the gap isn't in the model. Real air usually rewards a smaller gap; not counted here.
- **Walls as structure (`shell()`):** 8 deep beams along the floor edges (front/back split where the
  shoulders curve in: 24 in deep at the ends, 41 in in the middle; sides ~39 in). Asked the whittle-agent for
  per-member material + Timoshenko shear — done within the hour (safety uses each member's strength; sweep
  leaves non-tube groups alone). Its advice taken: check the foam's shear on Caliper's side (cautious: all
  of it in the foam), mind skin wrinkling (glass on 1 in XPS wrinkles at ~42 MPa, well under its 200), local
  axes. Not taken yet: walls at mid-height with links (floor-line axis is the safe side).
  - Walls are strong: PMF skins ≥ 6.4–6.9×, foam ≥ 24×; one layer of glass ≥ 5.7× (wrinkling-limited).
    Stiff too: wall stiffness ×100 changes the frame by 3%; ×0.01 drops it to 1.4×.
  - **Counting them doesn't lighten the frame**: they carry the walls' and roof's weight to where the box is
    fastened — the X's four tips — which is where the X arms are weakest. As drawn 1.69× → 2.0×, sag 0.97 →
    0.71 in; lightest ≥ 3.5× (exhaustive over 4,700 tube combinations, not just the sweep's path): tubes-only
    46.0 lb, walls 47.7 lb (PMF) / 46.5 lb (glass). Fastening the front wall's middle to the riser top with a
    steel tab: 43.6 lb. The 2 in shank in the receiver (solid bar at 3.5×) sets the floor either way; a
    5/16 wall shank gives 3.3× at 36.8 lb.
  - Fixings: a corner fixing carries ~37 lbf on a bump.
- **Frame v15 (adopted, run station 6):** shank 2x2 solid, riser 2.5x2.5x⅛, spine 2.5x2.5x⅛, X 1.5x1.5x0.083;
  47.7 lb of tube + 3 lb gusset = 50.5 lb; 4.46× (x_back_right), sag 0.31 in on a bump.
- **Fiberglass:** one layer of 6 oz in epoxy weighs less than PMF (47.5 vs 52.3 lb box) and is ~15× stiffer
  and ~3.5× stronger as a skin (wrinkling-limited on 1 in XPS); two layers 53.7 lb. Box BUILD left at PMF
  (Theo's pick) — try it under **Built from**.
- **Glitch:** the server crashed twice on start (SIGSEGV, SIGABRT) while loading the design, with the full
  test suite and another session's whittle tests running; not reproducible after (sequential, threaded and
  real-server parallel requests all fine). Watch for it.
- **whittle sweep note:** with glass walls the sweep stopped at 3.45× ("nothing reaches 3.5×") though a
  heavier shank was in its list — the exhaustive search found 46.5 lb at 3.53×. Told the whittle-agent.
- Tests: `test_frame_study.py` +2, `test_construction.py` +1. Full suite green.
- Commit: `45ddc9f`

### 2026-10-28 · CALI-42 + CALI-43 · Room for the mattress, curvier sides, and an X frame that carries the box as built
- **Why:** Theo: widen the box so a twin fits inside the 1 in walls (~77 in) — now wider than the Leaf, the
  sides should be pulled in by the drag study, "keeping the mattress + 6 in width at the base"; then 1 in tube,
  and an X under the floor leaning on the plywood, with a gusset where it meets a 2 in beam in the middle.
- **Reading of "mattress + 6 in":** the bottom 6 in above the floor (a 6 in mattress) keeps the full width;
  above it the sides may come in. The mattress thickness is one number (`MATTRESS`) if he meant otherwise.
- **CALI-42 — the box (v6):** 77 × 40 × 41 in, floor flat and full size. One section function: full-width
  base to `wall_h`, then `tumble` (roof edges drawn in) + `shoulder` (straight → round, a superellipse), a
  rounded `nose_*` above the walls, a `tail_*` taper; a ruled loft of ~20 sections (0.01–0.7 s a build).
  `construction()` cuts the same surfaces into panels (flat end panels inside the shell, flat base strips,
  bent shoulder/roof shell; posts bevel-cut to meet the shell). 58.9 lb plain.
- **Reusable:** `keeps(params, build)` (boxes a part must hold clear) → `ParametricStudy.keep()` + Caliper's
  own surface sampler (`aero.keep_check`) on every station — whittle's KeepOut averaged over vertices, so a
  small cut-in passed its slack (told the whittle-agent; it now adds the deepest vertex). Report says whether
  each keep still fits with the BUILD tried; viewport draws it. `RANGES` = the part's own search ranges
  (unlisted numbers left unticked). Signature ignores RANGES/LAYOUTS, keeps keeps().
- **Drag study (8 numbers, behind leaf_rear, 65 mph, effort 0.6, 2,738 builds, 40 min):**
  start 313 N (the 74 in box was 293). Design 1: −4% volume, 16.8 lbf ≈ 3.3 kWh/100 mi saved; **design 2:
  −9%, 22.2 lbf ≈ 4.4**; design 3: −14%, 23.8 lbf ≈ 4.7. It wants the walls as low as the mattress allows
  (`wall_h` 170 mm, its limit), the **front rounded hard above the walls** (`nose_pinch` at its 300 mm limit
  over ~400 mm), modest tumble (2–4 in), slightly round shoulders (1.3–1.4), a long tail. Every design clear
  of the mattress. Lighter too: 54.0 / 52.3 / 50.9 lb vs 58.9. Not adopted — Theo picks.
- **CALI-43 — loads where they are:** `construction.load_points()` (each piece's weight spread over its
  area/length, ~100 mm apart; sums and balances exactly — 58.92 lb, CoG unchanged) + `design_loads()` (the
  design's parts + payload on top of the floor). `frame_study.study(from_design=True)` lands each on the
  nearest `"carries"` member as a point load (bins of 50 mm). First cut split members into 150 mm pieces —
  the whittle-agent caught that buckling would then be checked over 150 mm; it added `point()` and members
  stay whole (same numbers: bending governs). Layouts (`LAYOUTS`), a run picker, the hardest-worked
  **welded** joint (a tube running straight through doesn't count, unless a bigger tube is in the way).
  Frames weigh as cut (`from_members` joins straight runs, drops stubs); a frame's `construction()` now lists
  only its other pieces (the gusset), its tubes come from `members()`.
- **The X frame (v13):** 2 in spine (tops flush), 1 in X spine-middle → corners, 1 in front/back edges, 3/16
  gusset slotted round the spine; 48.4 lb as drawn (shank 16″, riser 8″, spine 50″, X 4 @ 42″, edges
  4 @ 37½″). Carrying box 58.9 + 100 lb payload, ×2.5 driving, target 3.5×:

  | layout | lightest at best safety | safety | sag | hitch standing |
  |---|---|---|---|---|
  | X only, spine to the middle | **64.7 lb** (X 2x2x0.083) | 2.38× | 0.69″ | 8,007 lb·in |
  | X + F/B edges, spine to back | 74.2 lb (X 1.5x1.5x0.083, edges 1x1x1/16) | 2.22× | 0.83″ | 8,592 |
  | X + F/B edges, spine to middle | 74.4 lb | 2.24× | 0.75″ | 8,524 |
  | X + all four edges | 79.1 lb | 2.17× | 0.87″ | 8,790 |
  | X + F/B edges, all 1 in | 78.9 lb (1x1x1/8) | 2.17× | 0.99″ | 8,784 |
  | X only, 1 in X | 54.1 lb — X arms fail | 1.33× | 1.38″ | 7,573 |

  **Every layout stops at the shank in the receiver** (2x2 solid bar, the biggest a 2 in receiver takes) —
  the load and how far back it sits, not the platform. X-only: 4.8× empty, 3.2× with 50 lb aboard, 2.4× with
  100. Joint at the X's middle ~2,700 lb·in per arm on a bump (gusset input, plate mode waits for Theo).
  The plywood + bonded foam walls stiffen the platform too; the study leaves them out (safe side).
- Tests: `test_aero.py` +5, `test_construction.py` +5, `test_frame_study.py` +4. Full suite green.
- Commit: `d9876cd`

### 2026-10-27 · CALI-41 · What it's built from — weight, balance and a shopping list
- **Why:** the frame study showed the hitch carries ~6,400 lb·in standing still, dominated by weight far
  behind the pin. Theo's priorities: lighten the back (mostly foam, 1 in steel instead of 2 in), and get to a
  ~60 lb box: ⅜ in plywood floor, four 2x2 corner posts, 1 in foam + PMF everywhere else. He also wants this
  reusable, not tuned to this one project — and it's the groundwork for the cut plan and CNC DXFs.
- **Design:** a part declares `BUILD` (choices) and `construction()` (pieces), like a frame declares
  `members()`. Choices live apart from PARAMS on purpose: a drag study searches PARAMS, and a floor-thickness
  change must not make that study "stale" — `shape_signature` now ignores BUILD/construction/members/supports
  (no stored signatures existed yet, so normalising trailing whitespace was free).
- **The box (v5, shape unchanged — STL bounds identical):** floor full 74×39 in, walls standing on it, front
  and back full width, sides between, roof on top; posts in the corners inside the foam. Handles the tail
  shapes too (bent panels by facets) for when Theo picks one. **56.1 lb**: ⅜ ply 21.9, PMF 14.6, XPS 10.1,
  posts 5.4, hardware allowance 3.1, sealer 1.0. CoG 19.5 in behind its front, 14.2 in above its floor.
  Shopping list: 1 sheet ⅜ ply, 4 sheets 1 in XPS, 2 × 8 ft 2x2, 5.9 yd of 60 in canvas, ~0.8 gal glue,
  ~0.9 gal paint.
- **The design:** frame (2 in tube as drawn) **71.6 lb** at 34.9 in behind the receiver mouth + box 56.1 lb at
  40.5 in → **127.7 lb, 4,774 lb·in** standing. The frame is the bigger half — CALI-42's target.
- **Steel weight:** whittle's FrameStudy weighs with AISC's design wall (0.93× nominal) — right for stiffness,
  ~7% light for weight. Caliper weighs tubes at nominal wall with rounded corners (2x2x⅛ → 3.08 lb/ft vs a
  catalog's 3.05); whittle's 67.1 lb ÷ 0.93 ≈ 72 agrees.
- **UI:** part → **Built from**: weight, CoG, pickers for every BUILD entry (what-if, nothing saved), *Use
  these*, made-of table, *To buy*. Design → **Weight & balance** with a payload. Red dot = CoG, green = hitch.
  Verified in the browser (¼ in floor what-if → 48.9 lb, hitch 4,481 lb·in; reset).
- Tests: `test_construction.py` (18) + 3 API tests. Full suite green.
- Commit: `42f5fee`

### 2026-10-27 · CALI-40 · Size the frame — and three bugs a tube frame shook out
- **Why:** with the camper shell shaped, Theo turned to the 2 in steel underframe: "how can we whittle that
  part down to use as little steel tube as possible", plus gussets at the riser's 90-90 jog for his CNC plasma.
  Voxels can't see a 1/8 in wall at 74 in, so the tube frame is a *frame* problem. Coordinated with the
  whittle-agent session: it built `FrameStudy` (beam solver, tube catalog within 1% of AISC HSS, sweep from as
  drawn to lightest-that-passes) on its `frame-study` branch; plate mode for the gussets comes after, fed by
  the frame's end forces at the jog. Theo's calls: frame first; no legs yet (driving case only).
- **Shipped — `src/caliper/frame_study.py`:** a part declares its own structure — `members(params)`
  (centrelines, tube, group, and the PARAMS that size it) and `supports(params)` — read in a separate process.
  Ends within 1 mm merge into joints; tubes map to whittle's catalog keys; two cases: `standing` (x1, the
  number to compare with the hitch rating) and `driving` (x2.5). The sweep's chosen tubes are written back
  into PARAMS as a parametric revision. API `/api/designs/{slug}/frame-study*`; the inspector shows **Size the
  frame** (not drag shaping) for any part with members()+supports(); previews fade the other parts.
- **Result on Theo's frame (100 lb on the rails, x2.5 driving):** as drawn (2x2, 1/4 shank) 67 lb of steel,
  weakest **1.45x** (riser, driving), sags 1.24 in. **The hitch holds 167 lb and 6,394 lb-in standing still**
  (15,984 at x2.5) vs ~2,450 lb-in for a typical Class II (350 lb x ~7 in). The sweep lightens the ladder first
  (1x1 rails, 2x2x0.083 cross members: -22 lb, *safer*), then puts steel at the jog (3x3 riser and upper shank,
  2x2 solid in the receiver): **3.32x at 63 lb** — it cannot reach 3.5x with what fits a 2 in receiver. The hitch
  moment barely moves with tube sizes (5.5–6.4k lb-in): it's the 100 lb box 40 in out. Matches the agent's run.
- **Three bugs the tube frame exposed, all fixed:**
  1. **Author replies were capped at 2,000 tokens** — a seven-tube frame + members() came back cut off
     mid-line, every attempt, as a baffling SyntaxError. Cap now 8,000, and a cut-off reply fails the build
     with the real reason ("write it more compactly").
  2. **`body_count` counted air as bodies.** Where a hollow tube's open end sits inside another tube, its bore
     is a sealed pocket whose surface is a separate mesh shell — a welded frame read as 6 "bodies", which also
     derailed the LLM's last attempts. Now counts B-rep solids when present, else only outward-facing shells.
  3. **The LLM author kept misplacing tubes** (corner-anchored boxes: cross members at y -93..-30 in). After
     three rounds I wrote the frame script myself — hollow tubes hollowed individually then fused with overlaps,
     members() whose ends meet at the joints (13 members, 12 joints), supports() for the receiver socket.
- **UI:** the run picker / stale-study guard for drag studies (`043a9cb`), a back link from an accidental "+ New
  design" (`1b37143`), and previews now fade other parts (the box hid the frame).
- **The Caliper server was SIGKILLed once** (exit 137, no traceback, RSS ~0.5 GB before and after) — external,
  most likely macOS memory pressure; not reproduced.
- **Tests:** +14 (`test_frame_study` 9, `test_measure` 3, `test_authoring` 2). 62 passed across the touched files.
- Commit: `117960e`

---

### 2026-10-27 · CALI-39 (follow-up) · The first real design, and what it taught the PARAMS contract
- **Theo's answers:** receiver ~9 in off the ground and 3 in forward of the bumper; ~51 in from there to the
  roof (60 in); teardrop/hatchback rear; Class II hitch; the hatch swings at most ~14 in behind the bumper.
  Built his design in the real UI, driving the shared browser pane: `a-cargo-box-on-the-trailer` — a Leaf
  rear stand-in (hatchback profile, a guess to correct), a `hatch_swing` envelope (both references), the
  2 in tube frame, and the box (tunable: tail params at 0). Clarify answered 3, assumed 2 (rear door,
  6 in roof fan — the rear door conflicts with tapering the tail; flagged to Theo). The box request's
  "must clear the hatch swing by at least 2 in" became `min_clearance(cargo_box, hatch_swing) >= 50.8`,
  validated (4 in today) and locked in.
- **Found live — the author put PARAMS *inside* `build()` and wrote `70.5 * 25.4`**, violating both halves
  of the convention, so the reader saw nothing. Fixed both sides: `read_params` also finds PARAMS at the
  top of `build()` and folds arithmetic on numbers (rewrite replaces the whole expression span, comment
  kept); the prompt now says *first statement, outside build(), finished numbers, inches in a comment* with
  an example. The next three parts all came back in the right shape.
- **The loop doing its job:** the frame came back with its ladder running 9 in forward under the car; two
  chat corrections (scoped to the frame) fixed it, measured each time (v3: ladder exactly -57..-18 in). A
  box request I sent while the frame was still selected was — correctly — treated as a frame change; it
  failed to build in 4 rounds and **the frame was left untouched** (never write a part that won't build).
- **Engineering flags raised with Theo:** Class II usually means a 1¼ in receiver (frame shank must match);
  the box's centre sits ~40 in behind the receiver — the empty box + frame (~110 lb est.) already puts ~3,800
  in·lb there vs ~2,000–2,500 for a typical Class II rating; departure angle ~8° at a 12 in floor.
- Tests: +2 (`test_aero`). 77 passed across aero/chat/API.
- Commit: `990fe80`

---

### 2026-10-27 · CALI-39 · Shape it for drag — numbers back, not a mesh
- **Why:** Theo's ask — whittle's carving makes organic, remeshed shapes that leave the parametric world;
  he wanted whittle to "remove mass … then replace with smooth, splined surfaces", and the whittle-agent
  session had ideas for using Caliper's parametric tools so the result is "a parametric part you could
  use directly". Synced with it over SendMessage; agreed split: **whittle drives** (its new
  `ParametricStudy`, same volume-vs-drag slider), **Caliper supplies `build(params)`**, in-process.
- **The contract:** a part's key dimensions live in a module-level `PARAMS` dict, `build(params)` merges
  overrides. `aero.read_params` / `write_params` read and rewrite it with `ast` **by source position**
  (UTF-8 byte offsets — a test pins a unicode comment ahead of it), so comments, layout and the build
  function survive byte-for-byte. Every authoring prompt now requires the convention (`chat.TUNABLE`), so
  parts are born tunable; a part without it gets a "Make it tunable" button that asks the chat.
- **The gap that mattered:** design parts were built with **empty params** (`_build_py_local` calls
  `build({})`), so their scripts hardcoded dimensions — nothing for a search to vary. The convention fixes
  it without threading spec parameters through the assembly loader.
- **Speed: `sandbox.BuildWorker`.** A sweep builds the script ~1000 times; the one-shot sandbox costs a
  fresh process + CadQuery import (1–2 s) each time. The warm worker (`_build_worker.py`) keeps one
  sandboxed process, compiles the script once, answers over a dedicated pipe (OCCT writes to stdout at the
  C level), kills/restarts on a timeout. Measured: start 1.2 s, then **0.13 s per build**; a failing fillet
  is a skipped candidate and the worker carries on.
- **Live result — the hitch box behind the Leaf stand-in** (obstacles from the whittle side; 4 params,
  effort 0.3, 105 km/h): 718 builds in 171 s. Best: `tail_len 500, tail_drop 146, tail_pinch 140,
  tail_edge_r 4` mm — a ~16° boat tail on top and sides, just under the model's ~20° separation threshold —
  **drag 83%, 11 lbf ≈ 2.2 kWh/100 mi saved, 7% of the volume**. Compare CALI-38's tail-only mesh carving:
  8.5 lbf, and its stations were inflated remeshes. Here the envelope stays **exactly** 39 x 74 x 41 in.
  `tail_len` hit its 500 mm bound — a longer taper is worth trying.
- **Verified in the browser:** the inspector lists the part's PARAMS with search ranges, runs the study
  with an ETA, previews a design in place (original as a ghost), and **"Use these numbers"** writes them
  into the script → v5, still `authored`/scripted, values rounded to 0.1 mm (finer than foam holds).
  Fixed on the way: the results table overflowed the inspector and scrolled the whole panel sideways.
- **Depends on whittle's uncommitted `physics-and-slider` branch** (installed editable into the caliper env
  — dry-run clean, adds scikit-image only). Kept on its own branch until that lands.
- **Tests:** +21 (`test_aero` 15 incl. two real studies at minimal effort, API 4, chat 1, worker via aero).
- Commit: `abb1d59`

---

### 2026-10-27 · CALI-31/32/33/38 · The design session in the browser, and the whittle bridge
- **Why (Theo, back after five weeks):** he wanted to *use* it — open the UI, design something real, and
  send it to his other project **whittle** (FEA + drag optimizer) for aero/load work, then bring it back.
  The real project: a **hitch cargo box behind his Nissan Leaf** — 74" W x 41" H x 39" D, 18" behind the
  car, XPS foam + poor man's fiberglass on a 2" steel tube frame. Asked to build the UI + updates, then
  walk him through it.
- **CALI-31 — jobs + SSE (`src/caliper/jobs.py`).** Long work runs on a worker; events stream over
  `GET /api/jobs/{id}/events`. Per-key locks: jobs sharing a key serialize, different keys run side by
  side (a whittle sweep doesn't block a chat). **Lost-update guard:** quick synchronous writes (units
  toggle, clarify answers, bring-back) take the same per-design lock as chat turns — otherwise a turn
  that loaded the design before the change would save over it. Heartbeats keep a 2-minute sweep's
  stream alive; the page de-dupes by sequence number and falls back to polling if the stream drops.
- **CALI-32 — the home page is now a viewport + a conversation** (`index.html`/`design.js`/`design.css`;
  the old panel moved to `/classic`, untouched). Chat left, Z-up viewer centre, inspector right. **Click a
  part to talk about it** (scope chip); the inspector shows its size in in/mm, the rules locked in on it,
  its history, the whittle panel, and an Advanced drawer with the script/spec. Proposals get Yes/No
  buttons. The thread redraws from `log.jsonl` — which meant **logging the reply text** (it only logged
  the action before). API in its own router, `src/caliper/design_api.py`.
- **CALI-33 — clarify round (`src/caliper/clarify.py`).** A new design drafts ≤5 questions that change
  geometry, each with a default; answers become requirements, **blanks are recorded as assumed**; "Just
  build it" assumes them all. The LLM call runs *outside* the design lock. A prompt written in inches
  turns on inch display (`Design.display_units`) — geometry stays mm, and the author is told to convert
  (an author told `UNITS: in` would model 25x too small).
- **CALI-38 — the whittle bridge (`src/caliper/whittle_bridge.py`).** Caliper drives whittle's own local
  server (`POST /api/parts`, `/api/jobs`, poll, fetch stations) — **no changes to whittle**, no shared env.
  Pre-fills flow (-X), mirror y, flat bottom, speed, budget, interior keep; `flow` and `dual`. Stations
  are filed under `designs/<slug>/whittle/<run>/`; **bring one back** → the part's revision becomes a mesh
  (`DesignStore.write_mesh_part`, new `whittled` origin), its script survives underneath, and rollback
  crosses back to it. Chat refuses to revise a whittled part's stale script (that would silently throw
  the carving away) and says how to get back.
- **Three things the LIVE runs against Theo's whittle taught, all acted on:**
  1. **Sheltering by merging fails.** I sent a frozen stand-in for the car's rear in the same upload so
     whittle's drag model would see the box sitting in its wake. Every station came back **0% removed**.
     whittle's flow study deforms one FFD lattice over everything uploaded; any move that reshapes the box
     also moves the frozen stand-in, the KeepOut penalty makes it infeasible, nothing beats the start. The
     path was **removed**, not shipped. Real shelter needs obstacle bodies in whittle — raised with the
     whittle-agent session.
  2. **Free air is the wrong question for a trailing box.** Free air: 20% removed → drag 55%, ~107 lbf
     saved at 65 mph — but it gets that by rounding the *front*, which behind a car sits in the wake.
     Restricting carving to the **tail** (`carve="tail"`, whittle's own `surfaces`) is the defensible
     study: **~37.5 N (8.4 lbf) ≈ 1.7 kWh/100 mi from ~8% of the box**, plateauing there. Allowing the strips
     past the car's sides "saved" 197 N, but only because the strips had to be voxel-wide and full-length,
     i.e. it rounded the front corners again — not trusted, not offered.
  3. **whittle's stations are voxel remeshes, ~½ voxel bigger than what was sent.** Station 0 ("0%
     removed") of a 74" box came back ~1" bigger per side, **+8% volume, bottom 0.94" lower** — and the
     "20%" station was really 13% of the box. This also broke my first context-stripping (containment
     test). Now Caliper **measures** removal against the part as built (station volume / part volume),
     and bringing a station back reports every side it grew (`grew_mm`), shown in the chat as a warning.
     The fake whittle in the tests inflates its stations too, so this can't regress unseen.
- **Coordinated with the whittle-agent session** (Theo's ask): sent it the bridge, the obstacle finding,
  the inflation numbers, and a proposed **parametric loop** — Caliper owns `build(params)` (tail taper,
  edge radii: buildable in foam), whittle exposes a fast *score* endpoint on its drag model, Caliper's
  optimizer searches. A parametric part comes back, not a mesh, and the remesh inflation disappears.
  Filed as **CALI-39**.
- **Tests:** +~110 (`test_jobs` 9, `test_clarify` 12, `test_whittle_bridge` 22, `test_design_api` 25, plus
  design/chat additions). Verified in the browser end to end against the real whittle (scratch designs
  dir, `caliper-web-scratch` launch config): units toggle, click-to-scope, a station previewed in place
  with the original as a ghost, bring-back, the chat refusing to revise the mesh, "roll it back" through
  chat, marking the car as a reference, and a tail-only study streamed from the page.
- Commit: `4fe957a`

---

### 2026-09-18 · CALI-30 · Feedback becomes a test
- **The idea M4 is built on** (conversational spec §2): a chat tool that only ever *edits* accumulates
  drift — you say "make it clear the rail", it happens, and nothing stops revision #14 from quietly
  undoing it. Caliper has a better option than any chat-with-CAD toy because measurement is already its
  source of truth: **measurable feedback is promoted into an assertion**, and the existing evaluator
  enforces it forever. The history then splits cleanly — `history.jsonl` holds the narrative,
  `spec.assert` / `assembly.assertions` hold the enforceable residue.
- **Shipped — `src/caliper/promote.py`:** draft → **validate** → park → accept/decline.
  - **Two levels, because Caliper has two namespaces.** A rule about one part (`bbox.dz <= 40`,
    `min_wall >= 2`) lands in that part's `spec.assert` and is enforced by the author loop; a rule
    *between* parts (`min_clearance(carriage, rail) >= 2`) lands in `assembly.assertions` and is checked
    whenever **anything** in the design changes. Drafting picks the level; validation uses the matching
    context. The vocabularies are declared in the module so the prompt can't drift from what the
    evaluator actually binds.
  - **Validated before it is ever offered.** Every candidate is *actually evaluated* against the current
    geometry. An expression that won't parse, names a probe that doesn't exist, or throws is never shown.
    Offering a broken test is worse than offering none. `holds_now` is tracked separately from `ok` —
    a rule you don't satisfy yet is legitimate to state, but the chat must not imply you comply.
  - **Proposed, never silent.** The proposal is parked in `pending.json` and the **next turn** accepts or
    declines it. `turn()` short-circuits on a parked proposal, so "yes" confirms the test instead of
    being routed to *refine* and authoring a pointless revision (tested).
  - **Honest about the unmeasurable.** "Less chunky" gets no proposal. But feedback phrased as an
    **obligation** ("it must…", "never…") that *can't* be measured now says so out loud, rather than
    letting the user assume the rule stuck. Ordinary tweaks ("a bit wider") are left alone — offering to
    enshrine every edit is noise.
  - **Id collisions.** A promoted design-level id may not shadow a **mate** id: both expand into
    `derived_assertions`, and "what did this change break?" is keyed by id, so a duplicate makes the
    answer ambiguous. `_unique_id` steps aside.
- **Two things the LIVE run exposed, both fixed:**
  1. **A promoted design-level rule was enforced but invisible to the author.** `prompt_context` listed
     mates and part-level assertions, not `assembly.assertions` — so a revision could unknowingly violate
     a rule the human had deliberately locked in, and we'd only catch it after building. Now
     `prompt_context` includes design rules that mention the part (**DESIGN RULES IN FORCE**). Measurable
     effect: before the fix, "move it within 1mm of the rail" produced *no movement at all* (still 6mm);
     after, the author moved it to **4mm** — as close as the locked-in `>= 3` rule allows.
  2. **The reply glossed over a change that didn't do what was asked.** If the rule drafted from the
     feedback doesn't hold, that *is* the evidence the edit missed — so the offer now says so:
     *"it does not hold right now (measured 4) — so the change didn't actually achieve what you asked
     for."*
- **Conflict detection (added on the back of that run).** Asking for something that contradicts a rule
  you already locked in was silently producing a no-op. `promote.conflicts` reduces `left OP literal` to
  an interval and reports an empty intersection over the *same* measurement — deliberately narrow (bands,
  booleans and non-literals return "can't reason about it", because a false conflict claim is worse than
  none). The offer names the clash, and accepting **retires** the rule it replaces, logged in history.
- **Tests:** +51 (47 `tests/test_promote.py`, 2 `test_chat`, 1 `test_design`, +1 part-level enforcement).
  Drafting patterns, validation rejections, parking round-trip incl. a corrupt slot, accept/decline
  landing in the right file and surviving a reload, replace-don't-duplicate, mate-id collision, the
  LLM path held to the *same* validation, a failed drafter never losing the user's edit, and the two
  that matter most: **the accepted rule catches the regression on a later revision**, with a control
  test proving the same change sails through when declined. **265 passed.**
- **VERIFIED LIVE** (real Claude calls): *"the carriage must clear the rail by at least 3mm"* → revised,
  then offered `carriage_rail_clearance: min_clearance(carriage, rail) >= 3` (✓ holds now, measured 6) →
  *"yes, lock it in"* → promoted onto the design → *"it should sit within 1mm of the rail"* → the reply
  named the contradiction with the rule just locked in and offered to replace it.
- Commit: `1855322`

---

### 2026-09-18 · CALI-29 · The chat turn handler — and the verb that didn't exist
- **The gap this closes (found by reading the code, not guessing):** there was **no code path to refine
  a part that lives inside an assembly.** `refine_authored` operated on a single-part run; assembly
  members were static `.py` files with no revision path. The core M4 interaction — *click the roller
  wheel, say what's wrong, watch it change* — had nothing behind it. `chat.refine_part` is that verb.
- **Shipped — `src/caliper/chat.py`:** `turn(store, message, scope=None)` → classify → act → re-measure
  → reply. It adds **no** geometry machinery; every action dispatches to the existing engine
  (`authoring.improve`, `authoring.refine_authored`, `DesignStore.restore`). What's new is the three
  things a conversation needs and the engine never had:
  1. **Scope is the selection.** Unscoped = the design, scoped = the clicked part. That one rule
     replaces the mode toggles and the "pick 1 / pick 2" ceremony.
  2. **Revisions see the design context.** `_working_spec` hands the author the goal, requirements,
     sibling parts, **mates that must keep holding**, enforced assertions, and a bounded feedback tail —
     on a *copy* of the spec, because `refine_authored` folds the instruction into `spec.intent` and
     that must not leak into the stored `spec.yaml` (tested). Multi-part designs also get an explicit
     **"build in the design's world coordinates"** instruction, since assembly parts carry no transform.
  3. **Every geometry change re-measures the WHOLE design** and the reply names what it **broke** (and
     fixed), by id, with the number. This is the thing that separates it from a chat wrapper around a
     CAD kernel.
- **Routing** mirrors intake (CALI-5): Claude when a key is present, a deterministic parser otherwise,
  injectable for tests, and it **degrades rather than crashing** — a malformed LLM reply falls back to
  offline with a stderr note. The offline rules deliberately **ask instead of guessing** when no part is
  named and nothing is being added ("5mm wider please" → a nudge to click or name a part), because a
  wrong guess spends a whole authoring run.
- **`revert` — added mid-task, because the reply was writing a cheque the handler couldn't cash.** The
  break message offered "roll back to the previous version" and there was no such verb; "roll it back"
  would have routed to *refine* and authored a revision. Now `revert_part` restores the previous
  snapshot **as a new revision** (so the undo is itself history), re-measures, and the offer names the
  phrase that actually works.
- **A part that never builds is never written.** Both `refine_part` and `author_part` require
  `res.geometry` before touching the store, so a failed revision leaves the part exactly as it was
  (tested). New parts get a baseline contract (`one_body`, `watertight`) — a spec with **no** assertions
  can never pass (`Report.all_pass` needs at least one considered check), so the author loop would have
  burned its whole round budget for nothing.
- **CLI:** `caliper chat <slug> "<message>" [--part ID] [--no-llm]` — narrates each step as it happens
  (the events `on_event` emits are exactly what CALI-31 will stream over SSE).
- **Tests:** +33 (30 `tests/test_chat.py`, 3 `tests/test_cli.py`). Routing (scope, named part, longest
  match, add-a-part, questions, ambiguity), LLM parse + target validation + fallback, honest refusals
  (unknown part, imported geometry with no script), logging, events, and the OCCT-gated core: refine
  inside an assembly rebuilds and re-measures; **a change that breaks another part is named in the same
  turn**; fixing it is reported; a non-building revision leaves the part alone; revert round-trips.
  **217 passed.**
- **VERIFIED LIVE** (real Claude calls, `caliper chat` against a seeded 2-part gantry):
  - *"make it 60mm wide and give it four M3 mounting holes on the top face"* on `carriage` → authored in
    1 round, **kept the world-coordinate `translate((0,40,0))`** (the context instruction worked), all
    checks green.
  - *"make it 120mm deep in the Y direction"* → the part itself passes every check, but the reply reads
    **"⚠ This change broke 1 design check(s) that passed before: carriage_clears_rail:
    interference(carriage, rail) <= 0 → actual=7200.0"**. Exactly the failure mode this task exists to
    catch.
  - *"roll it back"* → restored v2 as v4, **"✓ That fixed: carriage_clears_rail / The whole design
    measures green."**
- Commit: `48a35fb`

---

### 2026-09-18 · CALI-28 · The Design object — a container for "the thing I am building"
- **Why (Theo, picking the project back up):** the engine works, but the webapp is a *control panel for
  the engine* — it asks the user to know LLM-vs-offline, run-vs-assembly, "author any part", and which
  two parts to pick before Insert un-greys. Every toggle is an internal seam leaking into the user's
  job. The new direction: the product is a **viewport + a conversation**; you state what you're
  building, click a part, and talk about that part. Written up as **M4** in
  `specs/caliper-conversational-spec.md`, with M5 (decomposition) behind it.
- **Decisions taken up front:** chat-first on a **single part** before decomposition (don't debug a new
  planner and a new UI at once) · the old panel is **demoted to an Advanced drawer**, not deleted (the
  escape hatch matters when the loop misbehaves) · assertion promotion is **proposed and confirmed**,
  never silent.
- **The idea that makes the history worth keeping:** measurable feedback is **promoted into the spec's
  `assert` block**. "The wheel must clear the rail" becomes `min_clearance(rail) >= 1.0` — a test the
  existing evaluator enforces on every later revision. The history then splits cleanly: `history.jsonl`
  holds the narrative, `spec.assert` holds the enforceable residue. That's what keeps prompt context
  bounded as a design grows, instead of stuffing an ever-growing transcript into every revision.
- **Shipped — `src/caliper/design.py`:** `Design` / `DesignPart` / `Requirement` (pydantic, YAML+JSON
  round-trip) and `DesignStore`, the only thing that writes inside a design:
  `designs/<slug>/{design.yaml, assembly.yaml, log.jsonl, parts/<id>/{part.py, spec.yaml,
  history.jsonl, versions/vNNN/}}`.
  - **`assembly.yaml` is the existing format** — part sources are written relative to the design root
    (`parts/<id>/part.py`), which `_resolve_source` already handles, so `evaluate_assembly`/`assemble`/
    `insert` consume a design untouched. **A single-part design is a one-part assembly** — no second
    code path, which is what makes "prove it on one part, grow into machines" safe.
  - **Append-only, snapshot every revision.** `write_part` writes the canonical `part.py`, snapshots
    `versions/vNNN/` (part.py + spec + report), updates both records, and appends history **in one
    step** — so the history can't drift out of sync with the geometry it describes. `restore` rolls
    back as a *new* revision, so the rollback is itself history.
  - **Cache invalidation (subtle, would have bitten):** `assembly._PART_CACHE` keys on (path, mtime); a
    same-tick rewrite could serve **stale geometry to the very re-measure meant to prove the change
    landed**. `write_part` now evicts the entry. Covered by a test that widens a part and re-measures.
  - `adopt_run` brings an existing `runs/run_NNNN/` in: an authored run keeps its `part.py` and stays
    revisable; a template run has only geometry, so it's marked `imported` and the assembly points at
    the run dir — honest that there's nothing to revise.
  - `prompt_context(part_id)` builds the **distilled** context a revision should see: goal,
    requirements, sibling parts, mates that must keep holding, enforced assertions, and a bounded tail
    of feedback — not a transcript.
- **CLI:** `caliper design new|list|show` — `show` prints requirements, the part tree with each part's
  feedback narrative, and then **measures the whole design** (tolerant: names a broken part instead of
  sinking the rest, inheriting CALI-27's discipline).
- **Tests:** +26 (23 `tests/test_design.py`, 3 `tests/test_cli.py`) — round-trip, slug collisions,
  versioning/snapshots, torn-history-line recovery, id validation (rejects `../escape`), requirement
  upsert, bounded prompt context, run adoption both ways, and OCCT-gated proof that a design measures
  through `evaluate_assembly` and that a revision is measured rather than cached. **184 passed.**
- **Verified by hand:** created a gantry design, seeded two parts + a refine + requirements,
  `caliper design show` printed the tree, the feedback narrative, and `ALL PASS`.
- `designs/` gitignored (user artifacts, like `runs/`).
- Commit: `658c52e`

---

### 2026-06-13 · CALI-27 · Hardening — fix the things Theo actually hit
- **Reported (Theo):** (1) confusing UI — "didn't know which options to click"; (2) "adding in new
  parts didn't seem to work"; (3) "the 'machine' generation only made part of the machine";
  (4) "I don't even remember where it's hosted."
- **Root cause of the partial machine (real bug):** `loadAssembly` fetched part STLs sequentially with
  **no `response.ok` check** — one slow/failed part threw out of the loop, leaving already-added parts
  on screen and never loading the rest. Fixed: parts load **in parallel**, each with its own error
  handling; the viewer renders everything that loaded and the error bar **names what broke and why**
  (status: "loaded 3/4 parts — see the error bar"). Progress text explains the first-load script builds.
- **Server tolerance:** new `assembly.load_parts_tolerant` — one broken part no longer sinks the whole
  assembly; `/api/assembly/{id}` returns `part_errors` per part and still measures what loaded. Build
  errors now surface the traceback's **last line** (the actual exception), not 300 chars of boilerplate.
  A stale error bar is cleared on each new load.
- **UI clarity:** a collapsible **"❓ How this works"** primer (build one part → refine → fit →
  assemblies/insert; which actions need the API key); intent label says **"describe one part"** (a
  machine = an assembly — likely the other reading of "generation only made part of the machine": `gen`
  authors ONE watertight part by design); tooltips on use-Claude/author/refine; the Insert hint now
  narrates each step ("left-click a part … 1 more … ready — Insert authors a part mating a ↔ b").
- **Where it runs:** README gains a top-level "▶ Run it" block — **`make serve` →
  `http://127.0.0.1:8000`, local only, not hosted anywhere**; TESTING.md opens with the same callout.
  README status/layout refreshed (was stale at "Phase 0").
- **Verified live in-browser (Preview MCP):** a deliberately-broken 2-part assembly renders the good
  part + names the broken one ("RuntimeError: demo: this part is intentionally broken"); the corner-leg
  machine still loads 4/4 ALL PASS; pick hints step through 0→1→2 correctly; error bar clears on the
  next load; zero console warnings.
- Tests: +2 (`load_parts_tolerant` names the broken part; `/api/assembly` returns `part_errors`, good
  part still serves, broken part 422s with a clear detail). **158 passed.**
  Commit: ab9db2c

### 2026-06-13 · CALI-25 + CALI-23 + CALI-26 · A whole (small) machine, with measured bolt alignment
- **The north-star stress test, passing:** a 4-part **corner leg** — two solid **20×40 mm bars** (a
  vertical post + a horizontal beam) meeting at a right angle, joined by a **gusset bracket** and
  standing on a **foot**, screwed together with M5s through **aligned holes** — `caliper assemble
  examples/machine.yaml` → **ALL PASS** (4 touch mates, no collisions, **3 bolt-hole-alignment checks at
  ~1e-15 mm**).
- **CALI-23 — parts built from a script at assemble time:** an assembly `Part.source` can now be a
  CadQuery `build(params)` **`.py`** (not just an STL/run-dir). `assembly._build_py_local` runs it in the
  sandbox (keeps the **B-rep** — so feature probes work), cached by path+mtime; `_build_py_part` poses
  it. The machine's 4 parts are committed scripts under `examples/machine/`, built in world coords.
- **CALI-25 — hole-alignment measurement (the new vocabulary):** `measure.holes_world(g)` returns a
  part's holes transformed into the assembly frame by its `pose`; `measure.min_hole_misalignment(a, b)`
  is the smallest perpendicular offset between a hole of `a` and a *near-parallel* hole of `b` (0 =
  coaxial → a screw passes straight through both). Bound into the assembly evaluator as
  `hole_misalignment(a, b)` / `holes_aligned(a, b, tol)`. Threaded = tap-diameter holes in the solid
  bars, clearance in the bracket/foot (the real FDM convention; no modeled helix — per CALI-12).
  Added `pose` to `Geometry`.
- **CALI-26 — collision shading in the viewer:** `/api/assembly/{id}` and `/api/insert` now return
  `collisions` (pairs with interference > 0); the viewer shades any colliding part **red** (resets to
  its role color otherwise). The webapp also serves `.py` parts as STL (builds the local mesh; the front
  end poses it), so script-built assemblies render.
- **Verified:** CLI `assemble examples/machine.yaml` → ALL PASS; in-browser (Preview MCP) the corner-leg
  loads, all 4 parts render with the bracket's **bolt holes visible**, ALL PASS, no collisions/red, no
  console errors. Negative tests confirm `hole_misalignment` *grows* with offset and the assertion fails.
- Tests: `test_assembly.py` +5 (script-build keeps B-rep + detects holes; misalignment 0-when-coaxial /
  grows-when-offset; deferred without holes; full eval pass + fail). **156 passed.**
- **Deferred:** mate lines in the viewer + per-part build cache invalidation across processes; threaded
  helix modeling (CALI-12); optimizer-in-author-loop (CALI-24, still queued).
  Commit: b2e4bb9

### 2026-06-13 · CALI-21c · Viewer UX — monitor-resize, middle-mouse pan, fit-to-view + adaptive grid
- **Reported (Theo, after plugging into a different monitor):** the 3D view didn't resize correctly,
  no middle-mouse panning, and it needed a proper recenter / stage sizing.
- **Monitor/DPI resize:** `resize()` now re-applies `renderer.setPixelRatio(min(dpr, 2))` every time
  (moving monitors changes `devicePixelRatio`; the old code set it once at init → stale → blurry/
  mis-sized). CSS now sizes the canvas (`#viewer canvas { width/height: 100% !important }`) while
  three.js sets only the draw buffer — so the canvas always fills the panel and the buffer matches DPI.
  Added a `window 'resize'` listener + a `matchMedia('(resolution: …dppx)')` watcher (re-armed each
  change) to catch DPI-only changes that don't fire the ResizeObserver. Bonus: this removes the benign
  `ResizeObserver loop` warning at its source (no more inline-style feedback).
- **Panning:** OrbitControls remapped CAD-style — `mouseButtons = {LEFT: ROTATE, MIDDLE: PAN, RIGHT:
  PAN}`, `screenSpacePanning = true` (was MIDDLE: dolly). Wheel-press-drag now pans. Pick-to-select
  guarded to **left button only** so a middle/right drag pans without selecting a part.
- **Recenter + adaptive stage:** a **⤢ fit** button (and `F` key) reframes whatever's on screen
  (`frameScene`/`frameAssembly` refactored onto a shared `frameBox(contentBox())`). The ground grid is
  now **sized to the content** (`fitGrid` — rounds up to 20 mm, floor 40 mm, positioned under the
  content) instead of a fixed 400 mm plane that dwarfed small parts.
- **Verified live in-browser (Preview MCP):** canvas fills the viewer and the buffer matches DPR
  (`bufferMatchesDpr: true`); resizing the viewport 1280→1100px re-fills correctly; loading two-posts +
  ⤢ fit recenters with a content-sized grid; zero console warnings/errors. Web-only change (no Python) —
  full suite still **153 passed**.
  Commit: c4aec8c

### 2026-06-13 · CALI-21b + CALI-20b · Webapp insert UI + assembly viewer — VERIFIED LIVE
- **What it is:** the CALI-21 headline, now **clickable in the browser**. Load an assembly, see all its
  parts in 3D, **click two parts to pick the interfaces**, choose a fit + intent, hit Insert → the LLM
  authors the bridging part, it drops into the scene (green), and the whole assembly is re-measured.
- **Backend (`server.py`):** `GET /api/assemblies` (lists every YAML under `CALIPER_ASSEMBLIES`, default
  `examples/`, that parses as an Assembly), `GET /api/assembly/{id}` (parts + poses + stl_urls + measured
  report), `GET /api/assembly/{id}/part/{pid}.stl` (serves a posed part's STL), `POST /api/insert`
  (wraps `insert.insert_part` → persists the authored part as a run → `add_part_to_assembly` → saves
  `<id>.inserted.yaml` → re-measures → returns the new part's stl_url + report + script + bridge info).
- **Frontend (`app.js`/`index.html`/`style.css`):** an Assemblies list; multi-part rendering (each part
  posed, colored by role — gray=fixed, blue=movable, **green=inserted**); **click-to-pick** via raycast
  (drag vs click disambiguated by pointer travel) with emissive highlight + a picks readout; an insert
  panel (intent / id / fit); the assembly report reuses `renderReport`. `window.__asm` debug seam
  (mirrors `__caliperSM`). Benign `ResizeObserver loop` warning filtered from the error bar.
- **Bug found & fixed (live):** `insert_spec` resolved a part `source` against `base_dir`, then
  `improve`→`load_references` re-resolved the *relative* result against `ref_base` → doubled the dir
  (`examples/examples/post.stl`). The CLI dodged it (it passed an absolute base_dir); the server's
  relative `examples` exposed it. Fix: `insert_spec` stores **absolute** reference paths.
- **VERIFIED LIVE in the browser (Preview MCP, real Claude API):** loaded `two-posts`, both posts render
  at x=±30; picked both (highlight + button enable confirmed); Insert → LLM authored the cross-bar in
  **1 round**, rendered green between the posts; report ALL PASS (both mates **0.21 mm**, nothing
  collides); saved as `insert_demo.inserted`. No console errors.
- Tests: `test_server.py` +5 — list/get assembly + serve part STL + insert route-through (faked author)
  + bad-between 400 + unknown-assembly 404. **153 passed.**
- **Deferred:** in-browser assembly *authoring* (build parts from intent at insert time) → CALI-23;
  per-part red/green collision shading → polish (the report already shows per-mate pass/fail).
  Commit: 914a791

### 2026-06-12 · CALI-21 · Insert-into-assembly — the north-star headline, end to end
- **What it is:** *"insert a support between the wheel and the XYZ assembly."* The whole spine converges:
  CALI-20 (the posed existing parts + N-body measurement) + CALI-19 (fit bands) + CALI-16/17/22 (the
  author loop) → the LLM writes a part **in assembly/world coordinates** that mates to two named
  interfaces at a target fit, **verified by measurement**, then it's added back to the assembly.
- **`insert.py`:** `insert_spec(asm, between, fit, …)` builds a spec whose **references are the existing
  parts, posed** and whose assertions are the two fit **bands** + no-interference with every other part
  + one-body/watertight. `_bridge()` finds the separation axis + the two facing faces; the enriched
  intent hands the author the interface bboxes, the gap, and the facing-face coordinates in world space
  so it builds *in place* (not at the origin). `insert_part()` runs the author loop; `add_part_to_
  assembly()` appends the new part (run-dir source, identity placement) + two `fit` mates.
- **CLI** `caliper insert <asm> --between a,b --as id --intent "…" --fit slip --save out.yaml` (+ `make
  insert`): authors, persists the part (STL + `part.py`), adds it to the assembly, and **re-measures the
  whole assembly** with the new part in place.
- **VERIFIED LIVE (real Claude API):**
  - `insert` two-posts (50 mm gap) → the LLM authored a cross-bar **first try (1 round)**, landing
    **0.21 mm clearance to each post** (dead centre of the slip band 0.12–0.30); the script reasons from
    the interface bboxes, applies the clearance, and `.box(...)` in world coords. Assembly re-measured →
    ALL PASS (`crossbar_post_left`/`right` at 0.21, nothing collides). Saved assembly re-`assemble`s green.
  - Also confirmed the other LLM paths live: `gen` (authored a 4-hole part, 1 build-heal + 1 revision);
    `refine` of an authored part ("6 mm taller in z") — edited the real `part.py` (`bar_height = 10+6`)
    while keeping both fits at 0.21 (CALI-22 `refine_authored` seeding).
- Tests: `test_insert.py` (6) — bridge-axis, spec (posed refs + fit bands + no-collision + one-body),
  bad-interface guards, add-to-assembly mates, end-to-end author (injected) that mates both. **148 passed.**
- **Deferred:** webapp insert UI → CALI-21b; assembly parts built from a spec/intent at assemble time →
  CALI-23. Insert authors the geometry directly today; the multi-param optimizer (CALI-19b) isn't yet
  folded into the authored path (LLM revises dimensions instead).
  Commit: 7fb4d32

### 2026-06-12 · CALI-19b · Multi-parameter optimizer — joint tuning for coupled fits
- **Why now:** CALI-19's tuner is **1-D** (one knob per failing check). Assembly fits *couple*: one
  clearance depends on two dimensions, or two mates fight over the same wall. Tuning one knob at a time
  stalls at a saddle the per-axis sweeps can't leave. The assembly spine needs joint N-D tuning.
- **`decide.tune_multi(spec, params, eval_fn, engine="coord")`:** searches the joint continuous space
  against a **global** objective — maximize `(all_pass, #passing, worst signed margin, −total
  normalized change)`. Worst-margin drives every assertion toward/over its threshold at once;
  change-from-init keeps the solution snug.
- **Engine = coordinate descent by default** — deterministic and *eval-frugal* (geometry rebuilds are
  the expensive thing): sweep each knob over a coarse grid + a refined local window against the global
  score, until a sweep stops improving. **Escalates to a global `scipy.optimize.differential_evolution`
  (seeded, deterministic) ONLY if coordinate descent can't reach feasibility** — i.e. the genuinely
  coupled case CD traps on. Cheap-first keeps separable problems off the expensive path.
- **`decide` route 0 (CALI-19b):** with ≥2 continuous knobs and a failing numeric check, tune the whole
  vector jointly; taken only if it improves (more passing / all-pass), else fall through to the 1-D +
  snug path. Single-knob specs are untouched — the common case stays 1-D.
- Tests: a deliberately **coupled** 2-knob problem (gap band on `W+D` + budget on `W*D`, feasible only
  asymmetric) — coordinate descent escalates to scipy and solves it; `engine="scipy"` solves it
  directly; a **separable** 2-knob problem is solved by CD alone (scipy spy asserts it's never called);
  `decide` routes coupled failures to the multi move. **142 passed.**
  Commit: a84397b

### 2026-06-12 · CALI-22 · Author-loop fit & refine — edit the real part, not a bracket
- **Why now:** the fit bug Theo hit — fit/refine rebuilt via the bracket generator, so they ignored an
  authored `part.py` (CALI-19 guarded them to *fail honestly*). Now they **edit the real part**: route
  through `improve()` **seeded with the existing script**, so the LLM revises `part.py` to clear a
  reference or apply a plain-language change — the front edge of CALI-21 (insert-into-assembly).
- **`authoring.improve(..., seed_script, seed_feedback, ref_base)`:** primes round 1 with an existing
  part + the new constraint, so the model revises rather than starting over. Same build-error +
  failing-measurement healing as `gen`.
- **`refit_authored(spec, script, …)`** — spec already carries the reference + fit assertion(s) (via
  `fit.attach_reference`); seeds the loop with `part.py` and feeds the fit checks. **`refine_authored(
  spec, script, instruction, …)`** — folds the instruction into `spec.intent` (so a later round can't
  quietly undo it) and seeds the loop.
- **CLI:** `caliper fit <authored-run> --fit slip` and `caliper refine <authored-run> "…"` now route
  through the author loop (no more "refuse authored" return-2). **Webapp:** `/api/fit` + `/api/refine`
  do the same (the 422 guards are gone); a shared `_finish_authored()` persists script+STL+refs.
  `/api/gen` refactored onto it too.
- Tests: `improve` seed-priming; `refit_authored` drives a 60→30 mm box to clear a reference (2 rounds,
  fed the failing `interference`); `refine_authored` intent-fold; CLI fit+refine route-through; server
  `/api/fit` + `/api/refine` route-through (replacing the old 422 guards). **138 passed.**
- **Live (LLM) path** needs `ANTHROPIC_API_KEY`; the routing is verified deterministically via injected
  authors. Webapp/CLI live runs are Theo's to drive.
  Commit: 72b0df4

### 2026-06-12 · CALI-20 · Assembly model — N parts + named mates + assembly assertions
- **Why now:** the single-part loop is complete; the north star ("a 3D printer 10ft tall", "insert a
  support between the wheel and the XYZ assembly") is fundamentally about *a collection of parts that fit
  together*. This is the heart of the assembly spine — and the lesson from the phone-stand failure
  (complexity scales by **decomposition into well-fit parts**, not one monolith).
- **`assembly.py`:** three pydantic models mirroring the single-part spec — `Part` (id + geometry
  `source` + **placement** position/rotation, role fixed|movable), `Mate` (a **named relationship between
  two parts**: `no_interference` / `clearance` / `fit` / `touch`), `Assembly` (parts + mates +
  assembly-level assertions). YAML/JSON round-trip; validates mate part-refs + dup ids.
- **Each mate expands to one measured assertion** (`mate_assertion`): "wheel & support mate at a slip
  fit" → `0.12 <= min_clearance(wheel, support) <= 0.30` — measured, not eyeballed. `touch` → a flush
  band `-tol <= min_clearance <= tol`; `fit` reuses CALI-19 fit bands.
- **`measure.py` — N-body substrate:** `pairwise_interference(parts)` (every unordered pair),
  `max_interference()` (worst overlap — "nothing collides"), `min_pair_clearance()` (tightest gap). The
  two-body probes already accepted any Geometry pair, so N-body = run the pair probe over every pair.
- **Evaluation reuses the single-part evaluator wholesale** — same safe AST interpreter, same signed
  margins (so a fit *band between two parts* is tunable too), same `Report`. Only the namespace differs:
  part ids → posed `Geometry`, fit probes take **two parts**. Posing is baked at load (`from_stl_posed`),
  so parts are measured *where they sit*.
- **`caliper assemble examples/assembly.yaml`** (+ `make assemble`) loads, lists parts/mates, measures.
- **Verified live:** the demo `post-stand` (base → post → cap, two `touch` mates + `max_interference()
  <= 0`) → **ALL PASS** (clearances 0.000, no collisions). A deliberately-overlapping pair → both the
  mate and the assembly assertion `fail`.
- Tests: `test_assembly.py` (13) — model round-trip/validation, N-body helpers, mate expansion,
  end-to-end posed-STL evaluation (pass + fail + fit band). **134 passed.**
- **Deferred:** webapp assembly viewer (multi-part 3D + mate viz) → CALI-20b. CLI + model + measurement
  is the substance; the viewer is presentation.
  Commit: c24aa9f

### 2026-06-12 · CALI-19 · Tolerances & fits as first-class
- **Why now:** the phone-stand failure (user-reported) was mostly *bad assertions*, not bad geometry —
  a contradictory `slot_fits_phone: 8 <= bbox.dx <= 12` (the part is ~75 mm wide; `bbox.dx` is the whole
  part, not the slot) + measurement noise (`min_wall 2.99` vs a hard `≥3.0`). The fix is a fits/tolerances
  vocabulary, not a smarter prompt alone.
- **`tolerance.py`:** printer-friendly **fit classes** (press/snug/slip/free/running) → `(lo, hi)`
  clearance bands (FDM ~absolute). Helpers `approx(x, nom, tol)`, `within`, `fits(clearance, kind)` bound
  into the evaluator namespace.
- **Evaluator:** two-sided band margins — `lo <= x <= hi` now yields a signed margin (distance to the
  nearest bound) so a fit band is **tunable** (was `None`). **Optimizer:** `tune_continuous` gains
  progressive refinement (4 shrinking rounds) to converge onto a narrow 0.2 mm band; `decide` skips the
  snug `prefer` for band targets so they centre in the band.
- **Surfaces:** `caliper fit --fit slip [--nominal]` + a webapp **fit-class dropdown** → a band
  assertion. Intake taught to prefer `approx`/bands over `==`/hard thresholds and to **never** assert an
  internal feature (slot) via `bbox.*` (the phone-stand bug, at the source).
- **Verified live:** `fit --fit slip` tuned a bracket **60 → 41.8 mm** → clearance **0.188 mm**, centre
  of the slip band. Browser dropdown wired + no console errors.
- **Also fixed the fit bug they hit:** fit/refine now **refuse LLM-authored parts** (part.py present)
  with a clear message instead of silently rebuilding a bracket — CLI + `/api/fit` + `/api/refine`.
  Proper fix (route through the author loop) tracked as CALI-22.
- Tests: `test_tolerance.py` (8) + band-margin + fit-class loop + authored guards. **121 passed.**
  Commit: 7d237cf

### 2026-06-12 · CALI-17 · Structural-edit loop — fix failing measurements, not just builds
- **Closes the two-actor loop** for LLM-authored parts (design spec §2/§5): the LLM revises its own
  script when a *measurement* fails, the same way CALI-16 healed build errors.
- **`authoring.improve(spec, author, max_rounds)`:** each round the LLM writes/revises `build(params)`,
  we build it sandboxed + measure it; a build error feeds back the **traceback**, a failing assertion
  feeds back the **report** (id + expr + actual + margin). Stops on green, an unchanged failure
  signature (oscillation), or the round cap — mirrors the bracket loop's rails (CALI-6). Author is
  injectable → fully tested without a key. Folds CALI-16's build-heal into the same loop.
- **CLI:** `caliper gen` now uses `improve` (`--max-rounds`), printing rounds + heals/revisions.
- **Webapp:** `POST /api/gen` (refactored `_finish()` shared with the bracket `_execute`) + a
  **"✦ author any part"** toggle that routes Build → `/api/gen`; the authored `part.py` is shown and
  persisted; `get_run` returns it so a reloaded gen part shows its script.
- **Verified live (CLI):** `gen "a hexagonal pen cup…"` → 4 rounds (2 build-heals + 2 revisions),
  honestly reported **"best effort"** — the 2 residual fails were a *contradictory intake-drafted
  assertion* (a hexagon can't be 60×60 in bbox) and *measurement noise* (min_wall 2.99 vs hard ≥3.0),
  not author misses. Good integrity signal — it doesn't fake a pass.
- **Verified in browser (Preview MCP):** "✦ author any part" → "a round coaster, 90mm, 4mm, 3mm raised
  lip" → **ALL PASS in 1 round**, rendered in 3D, authored CadQuery shown in the script panel. No
  console errors.
- Tests: 4 `improve` tests + `/api/gen` server test. **110 passed.** Commit: 6ee3e52
- Roadmap stamped: next is the **assembly spine** — CALI-19 (tolerances & fits), CALI-20 (assembly
  model), CALI-21 (insert-into-assembly).

### 2026-06-12 · CALI-16 · LLM-authored generator (the spec's primary strategy)
- **Why:** the MVP shipped one hardcoded part family; the LLM only drafted a spec. The design spec's
  headline generation strategy (§2) is an **LLM-authored parametric script**. This builds it — the
  difference between "a bracket parameter optimizer" and the measurement-grounded vibe-CAD loop.
- **Sandbox** (`sandbox.py` + `_sandbox_runner.py`): authored scripts run in a **subprocess** (timeout,
  temp cwd), export **STEP** (keeps the B-rep so hole/face probes survive the process boundary), parent
  re-imports → `Geometry`. Any failure → structured `{error, traceback}` (the "stack trace" channel).
  Local-trust threat model; a hard sandbox (container/net-cutoff) is logged for untrusted use.
- **Author** (`authoring.py`): spec → `build(params)` script; on build error, retry with the traceback
  (bounded). The LLM call is **injectable** so author+heal is fully tested without a key.
- **CLI/wiring:** `caliper gen "<intent>"` / `make gen` — intake → author → build (self-heal) → measure
  → report → persist, storing `part.py` (the human-editable source of truth). Bracket path untouched.
- **Verified live** (claude-sonnet-4-6): `gen "a cylindrical desk cable grommet, 40mm OD, 30mm bore,
  25mm tall, 5mm flange"` → the LLM wrote a real hollow **tube + flange union** (with reasoning
  comments), built on attempt 1, watertight, correct OD/height/printable walls, **7/8 asserts pass**.
  The 1 fail is a measurement nuance (`largest_through_bore` counts the tube's outer wall as a bore →
  CALI-18), not an authoring miss.
- **Two LLM-intake bugs fixed along the way** (intake/refine had been silently dead for this model):
  (1) the **assistant-prefill** trick (`{`) made `claude-sonnet-4-6` 400 → always fell back to the
  offline bracket; removed it. (2) **schema-laxness** — model drafts didn't match the schema; added a
  precise schema+vocabulary prompt and `normalize_spec_dict()` (tolerant coercion). Now `gen` produces a
  faithful `desk_cable_grommet` spec, not a bracket.
- Tests: `test_sandbox.py` (5) + `test_authoring.py` (6) + CLI gen wiring + intake-normalize. **105
  passed.** Commit: c44403a

### 2026-06-12 · CALI-10 · Webapp fit UI + reference pose (in-3D placement)
- **Why:** fit was computed in baked coordinates — the reference had no pose, so it only "worked"
  because the demo obstacle STL was hand-authored in the bracket's frame. Real STLs (centered on their
  own origin) would land on top of the part. Fix: give references a **pose** and let you set it in 3D.
- **Reference pose:** `Reference` gains `position` (mm) + `rotation` (deg, three.js XYZ euler).
  `measure.pose_matrix` (scipy `XYZ` intrinsic, matches three.js) + `Geometry.from_stl_posed` bake the
  pose at load, so the fit probes stay pose-agnostic and the measured pose == what you see.
- **Backend:** `POST /api/fit` (base64 reference STL + pose + clearance/no-overlap + optional `free`
  param) → attaches a posed reference, promotes a size param, runs the loop, persists. Reference STL is
  copied into the run dir + recorded in `meta.references` (pose + serve url); served at
  `/api/runs/{id}/ref/{ref_id}.stl`; `get_run` returns references so a reloaded fit re-renders. Shared
  fit logic factored into `caliper/fit.py` (used by CLI + server; CLI `_cmd_fit` refactored onto it).
- **Front end (no-build):** vendored `TransformControls` (r160). Import an STL → renders
  **semi-transparent** with a move/rotate **gizmo** (W/E keys, mode buttons) → **Fit** reads the pose,
  POSTs, swaps in the resized part. The viewer now renders the part in its **true build frame** (no
  `geom.center()`) and frames on the combined part+reference bbox, so both share one coordinate system.
  Loading a past fit run re-renders its reference at the stored pose.
- **Verified in a real browser (Preview MCP):** build → import a box STL (gizmo appears) → Fit → server
  resizes + re-renders; loaded run_0026 shows the blue bracket pulled back from the orange reference at
  `[52,0,2]` with ALL PASS and `min_clearance(obstacle) actual=3`. No console errors.
- **Known caveat:** `/api/fit` is synchronous; a *coincident full-bracket* reference took ~30s (many
  mesh booleans × optimizer samples). A simple obstacle box is seconds. Logged as a follow-up.
- Tests: `tests/test_server.py` fit end-to-end + 404 (now **92 passed**). Commit: 6f048a8

### 2026-06-12 · CALI-10 · References / fit-to-reference (M3)
- **Measurements (real now, no longer deferred):** `measure.interference(g, ref)` → overlap volume in
  mm³ via a robust mesh boolean (manifold3d), with an AABB short-circuit and a containment-sampling
  fallback if the boolean kernel is missing; `measure.min_clearance(g, ref)` → signed gap in mm
  (positive = thinnest air gap from surface-proximity sampling, negative = deepest penetration). Both
  operate on meshes so they work directly on imported STL references. A `_as_mesh` coercer accepts a
  `Geometry`, a raw mesh, or a wrapper.
- **Reference binding:** `evaluate.load_references(spec, base_dir)` loads each `role: fixed` STL into a
  `Geometry`; `build_context`/`evaluate` take a `references=` map and bind `interference`/`min_clearance`
  to the real geometry. An *unloaded* reference resolves to an opaque handle so a fit check errors
  loudly instead of silently passing. `loop.make_eval_fn(references=…)` loads once and caches.
- **Snug fit:** `decide` auto-routes any failing `interference`/`min_clearance` assertion to a size
  parameter (`FIT_PARAM_PREFERENCE`), no per-spec id wiring. `tune_continuous(prefer=…)` adds a
  minimal-change objective: among feasible candidates pick the one closest to the original size, so the
  part shrinks *just enough* to clear (not down to the floor).
- **CLI/UX:** `caliper fit SOURCE --ref ID=FILE.stl [--min-clearance MM] [--no-overlap] [--free PARAM]`
  attaches the reference + fit assertion(s), promotes a fixed size param to a continuous range, runs the
  loop, persists a new run. Defaults to no-collision if no constraint given. `make fit`. Demo fixture
  `examples/obstacle.stl` (+ `make_obstacle.py`); `.gitignore` keeps `examples/**/*.stl`.
- **Verified end-to-end:** 60mm bracket vs a block at x∈[42,62] → fit shrinks the leg to 39mm for a
  clean ≥2mm clearance (`min-clearance 2`), or to 42mm just-touching for no-overlap. Tests:
  `tests/test_references.py` (11) + 2 CLI fit tests; updated the two evaluator/measure tests that
  assumed deferral. Full suite **90 passed**.
- Commit: d402e38

### 2026-06-12 · CALI-15 · Recent parts (+ hole-count hang fix)
- Browse/load past runs instead of always generating new. Persist `report.json` + `meta.json`
  (part, status, label, timestamp) per run; `GET /api/runs` (list) + `GET /api/runs/{id}` (load spec +
  report + STL without rebuilding; re-evaluates only for legacy runs). Front end: "Recent parts" panel,
  click to load the spec/report/mesh, active highlight, refresh after each run/refine; refine forks a new run.
- **Bug found while testing (real hang):** intent "…for **2020** with **two** M6 holes" mis-parsed the
  extrusion size 2020 as the hole count → generator tried to drill 2020 holes → CadQuery hung (POST
  never returned). Fixed: `_parse_holes` anchors the count on "holes" and limits it to a 1–2 digit /
  word number (so 2020 can't be the count) + clamp 1–12; defensively clamp `holes_per_leg ≤ 8` in the
  generator so no bad count can ever hang the kernel.
- Verified in-browser: build (1 iter, fast), new part tops the list with its label/timestamp, clicking
  an older run loads it (incl. legacy re-evaluate). Tests: **76 passed** (+5: list/load, parse, clamp).
- Commit: b582b54

### 2026-06-12 · CALI-9 · SpaceMouse: grid rotates with the part
- Feedback (real-use): with the SpaceMouse, the part rotated/panned/zoomed but the ground grid didn't
  rotate (it panned/zoomed fine). Cause: rotation spun the model *group* while the grid was parented to
  the world; pan/zoom move the camera so the grid followed those but not rotation.
- Fix: parent the GridHelper to `modelGroup` so rotation carries the plane with the part — pan/zoom
  (camera) and rotation (group) are now visually consistent. Verified render (no regression); rotation
  feel pending Theo's confirmation on hardware. 71 passed.
- Commit: cae162f

### 2026-06-12 · CALI-14 · SpaceMouse NL-Proxy (driver coexistence) — phase 1
- WebHID needs the user to quit 3DxWare (raw HID can't be shared — confirmed on Theo's SpaceMouse
  Compact `256f:c635`: "Failed to open the device" while the driver holds it). CALI-14 adds a *driver*
  path that coexists with Fusion.
- Researched the integration: NL-Proxy at `https://127.51.68.120:8181/3dconnexion/nlproxy`, WAMP/WSS,
  a driver-installed cert, and 3Dconnexion's `_3Dconnexion` lib driving the camera via navlib callbacks.
- Phase 1 shipped: UI mode toggle (WebHID | Driver/NL-Proxy beta); driver mode loads the proxy lib,
  instantiates `_3Dconnexion`, attempts connect, and reports the API surface + errors on-screen (cert
  hint included). Verified the graceful-failure path in the preview (no driver → clear error, no crash).
  Cannot verify the happy path here — needs Theo's hardware + 3DxWare; phase 2 (camera nav) follows the
  on-screen telemetry. 71 passed.
- Commit: 9420ca8

### 2026-06-12 · CALI-9 · webapp fix — vendor three.js locally (no CDN)
- Bug (real-use): on Theo's machine the Build button did nothing + a 404 in devtools. Cause: three.js
  was imported from the **unpkg CDN**; when that's blocked/offline/flaky the module import fails and
  `app.js` never finishes loading, so no event handlers attach. (Worked in the test browser where the
  CDN resolved — hence missed.)
- Fix: **vendor three.js locally** (`web/static/vendor/three/` — three.module.js + OrbitControls +
  STLLoader) and point the import map at local paths. App is now self-contained and works offline.
- Also: `<link rel="icon" href="data:,">` to kill the noisy favicon 404; an on-page error bar that
  shows load/runtime errors (so a dead button is never silent again); recursive package-data glob.
- Verified in-browser: zero external requests (all `localhost`), build → ALL PASS + render. 71 passed.
- Commit: 95a2e4a

### 2026-06-11 · 🎉 M2 COMPLETE · CALI-9 · webapp + SpaceMouse
- **FastAPI backend** (`server.py`): `/api/run`, `/api/refine`, `/api/runs/{id}/part.stl`,
  `/api/health` — reuse the library; persist runs; serve a no-build front end. `caliper serve` +
  `make serve`.
- **Front end** (`web/static`, no build step — three.js ESM via import map): intent box, refine box,
  measurement report panel (✓/✗ + margins + changes + clarify question), spec view, STL download, and
  a three.js viewer (STL loader + orbit, grid, lighting).
- **3Dconnexion SpaceMouse** (Theo's key ask) via **WebHID**: "Connect SpaceMouse" button →
  `navigator.hid`, 6DOF int16 axes → model rotate + camera pan/dolly, deadzone/gains tweakable, live
  axis readout, graceful fallback to mouse. Works in Chrome/Edge over localhost.
- **Verified in a real browser** (preview MCP): page loads error-free, `Build it` → ALL PASS report +
  bracket rendered in 3D; `Refine "make the holes 8mm and add a rib"` → "hole Ø 5.2 → 8.0, rib 0→1",
  re-measured, viewer reloaded the new mesh; STL downloads. Screenshotted both.
- Fixes found via the browser/test loop: FastAPI body models must be module-level under
  `from __future__ import annotations` (else 422); refine parser now handles "8mm" (no space) and
  prefers an explicit mm value over an M-size; a TDZ bug (`smOn` read before init in the render loop);
  dev `Cache-Control: no-store` so the browser never serves a stale module.
- Tests: **71 passed** (added server tests via FastAPI TestClient + refine regressions).
- Commit: 3c78fff

### 2026-06-11 · CALI-1.M1 · refine parser — per-side & word-number hole counts
- Real-use gap: "only do one hole on each side … in the middle" wasn't recognized (parser only knew
  digit + plural "N holes" as a *total*).
- Now the count parser accepts singular "hole", word-numbers ("one".."ten"), and **per-flange**
  phrasing ("on each side", "per leg") → doubles to the total. A single hole per flange is centred
  by the generator's positioning; "middle"/"centre" is acknowledged in the change list.
- Tests: **63 passed** (added 2). Verified the user's exact instruction → hole count 4 → 2,
  `bolt_pattern count=2`, ALL PASS, new STL.
- Commit: c9523c8

### 2026-06-11 · 🎉 M1 COMPLETE · CALI-1.M1 · refinement loop (one iteration cycle)
- New `refine.py`: a natural-language refinement → mutated spec. Offline deterministic parser for the
  common bracket edits (hole Ø, hole count, bolt spacing, wall, cable bore, ribs) plus an LLM path
  with offline fallback. Crucially mutates the *generator-read parameters* and re-syncs dependent
  assertions (e.g. a hole-Ø change updates both `hole_d` and the `bolt_pattern` assertion), so the
  change flows to the mesh, not just the acceptance text.
- Wired hole geometry into the generator: `BracketParams.from_spec` now reads `hole_d`/`hole_count`;
  intake emits them as parameters. (Backward compatible — defaults unchanged.)
- CLI: `caliper refine <run-dir|spec> "<instruction>"` loads a prior run, applies the change, re-runs
  the loop, emits a new run/STL. `_run_and_emit` shared with `run`. `make refine` target added.
- Demo: `run` → 4×Ø5.2; `refine "make the holes 8 mm"` → `bolt_pattern` re-synced to diameter=8.0,
  ALL PASS, new STL whose bytes differ (geometry changed; same triangle count). Optimizer tune
  already lived in the loop (CALI-6/7), so this completes the M1 "one NL refinement + one tune" cycle.
- Tests: **61 passed** (M1 added 14, incl. an OCCT end-to-end proving the rebuilt part has 4×Ø8 holes).
- Commits: `f78da23` (refinement loop), `cd857a4` (`make refine` target).

### 2026-06-11 · CALI-0 · canonical OCCT env via micromamba (Plan B) + zero-activation workflow
- Anaconda's classic solver stalled 55+ min on cadquery. Switched to standalone **micromamba**
  (osx-arm64), which solved + built the env in <1 min at `/opt/anaconda3/envs/caliper`:
  **cadquery 2.7.0 / occt 7.8.1 / ocp 7.8.1.2 / python 3.11**. Then `pip install -r requirements-pip.txt`.
- cadquery 2.7 dropped the `nptyping` dep → no numpy shim needed (unlike the pip-2.4 scratch venv).
- **`make test` → 47 passed** in the canonical env (auto-resolves the prefix), confirming the code
  works on cadquery 2.7 (not just the 2.4 used for the earlier scratch verification). CLI run → STL ✓.
- Editable-installed the package (`caliper` command) and added `make install`/`make run` targets that
  resolve the env python directly — no shell activation needed. Updated README/environment.yml to
  recommend the micromamba recipe.
- Commits: `e999d31` (micromamba env), `2c64680` (make targets + zero-activation docs).

### 2026-06-11 · 🎉 M0 COMPLETE · CALI-2/4/8 verified end-to-end with real geometry
- Verified the OCCT-dependent path. Fixed a generator bug: the CadQuery `"XZ"` plane normal is
  `(0,-1,0)`, so `extrude` is sign-defined and left the body off-centre on Y (bolt holes landed at
  the flange edge). Now recentre from the actual bounding box.
- **CALI-4** generator confirmed: corner bracket builds watertight, one body, 4×Ø5.2 holes on the
  bolt circle, optional Ø10 cable bore.
- **CALI-2** B-rep hole detection + `holes_matching(on=circle(60), count=4)` confirmed.
- **CALI-8** `caliper run "...four M5 holes and a cable pass-through" --no-llm --yes` → draft spec →
  clarify gate → loop → **ALL PASS** (bbox [60,20,60], min_wall 2.99, 4×Ø5.2 ✓, mass 8.1 g,
  watertight 1 body, bore Ø10) → 128 KB `runs/run_0000/part.stl`.
- **Full suite: 47 passed.** Verified in a pip CadQuery scratch venv (numpy-2 alias shim for the
  abandoned `nptyping`) because the conda env was still solving; re-confirmed later in the conda env.
- Commit: `ff8e154`.

### 2026-06-11 · CALI-6, CALI-7, CALI-8 · loop controller, decide, CLI
- **CALI-7** decide: continuous route (1-D grid+refine optimizer over a continuous param, scored by
  all_pass/pass-count/margin) and a structural route (bump a discrete param); defers to LLM when
  neither applies. Verified: a mass-over-budget failure is fixed by tuning `wall`.
- **CALI-6** loop controller: generate→build→sense→evaluate→decide with iteration cap, oscillation
  detection, run persistence (`runs/<id>/` spec+report+STL). Verified: converges, caps, detects
  oscillation, surfaces build failures. Injected `eval_fn` keeps it kernel-free for tests.
- **CALI-8** CLI: `caliper run "<intent>"` one-shot; `--no-llm`/`--yes` for reproducible runs; the
  ask-don't-assume clarify gate blocks non-interactive builds. Gate verified; end-to-end smoke
  (real STL) is OCCT-gated.
- Whole suite: **39 passed, 4 skipped** (CadQuery-only) in a clean venv.
- Commit: `a223b13`.

### 2026-06-11 · CALI-1, CALI-3, CALI-5 verified; CALI-2, CALI-4 written
- **CALI-1** spec schema: pydantic models (continuous/discrete/fixed params, references, machine stub,
  assertions under the `assert` alias); lossless YAML/JSON round-trip; validation on bad input.
- **CALI-3** evaluator: safe AST interpreter (no `eval`), signed margins for comparisons, compound
  `and` reports the binding margin, deferred probes (e.g. `interference`) marked `deferred` not failed.
- **CALI-5** intake: deterministic offline drafting for the bracket family (parses size, hole spec,
  extrusion width, cable), ask-don't-assume clarify gate, LLM path with offline fallback.
- **CALI-2** measurement API: mesh side verified (bbox, volume, mass, watertight, body_count, ray-cast
  `min_wall_thickness`, deferred probes); B-rep hole detection written, OCCT-gated.
- **CALI-4** corner-bracket CadQuery generator written (L-profile extrude, per-leg bolt holes, optional
  ribs + cable bore, structured build-error capture); OCCT-gated.
- Tests: **29 passed, 3 skipped** (CadQuery-only) in a throwaway venv. Added `rtree` dependency
  (trimesh ray casting needs it for `min_wall_thickness`).
- Commit: `0d93efa`.

### 2026-06-11 · CALI-0 · project scaffolding + environment
- Initialized local git repo. Created `src/caliper/` package layout, `tests/`, `pm/`, `nightshift/`.
- Stood up the .md PM system: `BOARD.md`, `TASKS.md`, `LOG.md`, `pm/README.md`.
- Adopted ai-night-shift conventions locally (loop/review/test guard) without cron — see `nightshift/`.
- Env: moved all non-OCCT deps to a pip layer (`requirements-pip.txt`) so conda only resolves
  `cadquery` under strict conda-forge priority (the full mixed-channel solve stalled).
- Decisions: conda for the env; nightshift conventions-only (no autonomous cron yet); start M0 core.
- Commits: `aa00b5d` (scaffolding + M0 skeleton), `45cd6b9` (lean conda env).
