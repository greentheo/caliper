# Caliper work log

Append-only. Newest first. One entry per shipped task or notable decision.
Format: `### YYYY-MM-DD · CALI-N · title` then what changed, tests, and the commit hash.

---

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
  breaking load in `test_release.py`.

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
