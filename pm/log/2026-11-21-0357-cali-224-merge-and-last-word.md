### 2026-11-21 · CALI-224 (#382) · #401 round two: main merged, and the job's last word never says lighter for a negative best

The foreman: #401 is signed clean (caliper-reviewer's review). #411 (stop points) merged first. Its CI's red was main's
old test, which the merge fixes.

**Merged main** (3387ebc, #407 and #411 in). One conflict, Lighten's end, resolved as agreed with the UI lane: stop,
then weigh against now, then write (`halt()`, `against_now(record, now_lb)`, `json.dump`). design.js merged without one.

**The job's last word** (`lighten.done_said`, from the review). The code already said "nothing lighter than now holds"
below zero, but nothing pinned it: a mutant dropping the `> 0` check survived. It's now a function, it says "nothing
lighter holds" as the studies' line does (the foreman's words), and it's pinned with the issue's numbers: −0.36, 0, none,
and 0.4 lb lighter.

Not mine: the page's lead line (`best.saved_lb > 0` in design.js) has no Python test. The review left that to caliper-ui.

**Mutants on the merge** (each anchor once, scratch copy), all 6 caught:
1. the study's steps not against now;
2. pictures counted as lightening holes;
3. an older run read from the bare part;
4. the studies' line saying lighter at or below zero;
5. a hole weighed at its sheet, not its depth;
6. the job's last word saying lighter at or below zero (new).

**Area tests** green at `-n 4` on the merge: the Lighten files, the stop points, the studies, waiting studies, Make it
better, step previews (137). **Full suite: CI.**
