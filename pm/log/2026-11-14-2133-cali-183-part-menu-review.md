### 2026-11-14 · CALI-183 (#294) · #302's review: every part job says its part; a design-wide job refuses at once; one rule for a mirror; the page's asks

reviewer-2's review and the foreman's list on #302.

- **Must-fix 1: every job that works on a part says which.** `design_api._on_part(slug, pid, …)` is the one helper. Load and Lighten, which had it, use it now too, and so do:
  - carve, whittle, frame, gussets and aero;
  - picture and cut plan.

  A test reads every `RUNNER.submit` and holds that each part job passes it, so a new route can't forget. The only jobs without it are the design-wide ones: chat, the first build, the package, clarify, goals and the scorecard.
  - **While any of them runs on the part,** the delete refuses in words ("… is being carved / whittled / sized / … : wait for it, or stop that first."). There's a stand-in job of each kind in a test.
  - **Before taking the design's lock,** the delete and the put back refuse at once while a design-wide job holds it: "a chat turn is working on the design: wait for it, or stop it first." That covers the first build and the build package too. They never wait silently behind a turn that may be writing the very part.
- **Must-fix 2: the mirror rule is `load_study.blocked()`'s.** A mirror reads `{"why": "mirror", "lighten"/"carve": "It mirrors side_right: change side_right and it follows, or break the mirror first"}`.
  - **Who reads it:** `studies.menu` (the part menu and the Studies page), the card (`better.offers`) and the panel (`p.blocked`, `#lightGo` and `#carveGo`). None of them can disagree now.
  - **The duplicate is gone:** `studies.menu`'s own mirror check came out.
- **Small asks:**
  1. **Focus goes back to what opened the menu,** the row or the view, after Escape or an item. After a delete, the row is gone, so focus goes to the tree's first row, never `<body>`. A click elsewhere keeps its own focus.
  2. **Shift+F10 or the menu key works from an empty chat box.** Selecting a part puts the cursor there. Delete doesn't work from the box.
  3. **A long-press that ends in `pointercancel` clears its flag,** and the next press clears a stale one, so no later tap is swallowed.
  4. **The delete's reply says what went with it and who follows the part:** "Its mate strips_clear_stool went with it. cap follows it: it keeps its numbers."
  5. **Put back of two parts names both,** source first.
  6. **The three surviving mutants are pinned.** The view's release is `viewUp` (past 5 px it's a pan; still, a right-click or Ctrl-click opens the menu), the long-press's lift is `swallowed` (taken once), and Put back's order is source then mirror. All three run in Node.

**Tests:** `tests/test_part_menu.py`, 36 now (20 new):
- the submit guard;
- 9 part-job kinds;
- 3 design-wide jobs;
- the reply's words;
- the mirror's one rule, across blocked, panel, menu and card;
- the view's release, the swallow, `pointercancel`, Put back's order, and focus and the menu key.

The earlier `studies.menu` mirror test now gives it `blocked`, as `design_state` does.
- **Mutants:** 17 on the rework, all caught. One survived until the mirror test also held that the menu says the mirror's words, not only that it greys them.
- **Around run:** 131 files: the menu's 98, plus everything that reads the load study, Lighten, studies or the card.
  - **11 failed on `blocked()`, the code's fault:** they call it with stand-in stores that have no `is_scripted`, and the new mirror lookup assumed a real one. A store it can't read a script from now counts as not a mirror.
  - **1 failed on a stale pin, the test's fault:** `test_lighten_joints`'s #222 pin read the load and Lighten jobs' old `meta={…"version": …}` literal. It now reads their `_on_part(…, version=…)` call.
  - **The 8 files** with failures pass now.
