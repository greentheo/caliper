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
