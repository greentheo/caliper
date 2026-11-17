### 2026-11-17 · CALI-198 (#327) · a part with no loads() is given one in the Scenarios editor, and then says it has one

Found on reviewer-2's aero walk, on a copy of the camper sample (the hitch cargo box). "Will it hold?" offered only "Say
what it must hold", a designer call, and no editor. A case added through the editor's route was checked, but the card
under the ✗ still said "It doesn't say what it must carry yet", with no Check it again and no Lighten.

**The code was wrong in two places:**
- the page's `loadView` returned before the Scenarios editor whenever `!p.loads`;
- `p.loads` was `"def loads(" in script`, so a case added in the editor never counted.

**Now:**
- **`scenarios.says_loads(store, pid, script=None)`** answers whether a part says what it must hold. That's true when
  its script has `loads()`, or when the person keeps a case in the editor. A kept case is either one they added, or an
  edit whose case the design has since dropped: the check still reads that edit (#312), so it counts. A save with every
  case off is already refused.
- **Every place that read the script alone now reads `says_loads`:**
  - the page's `p.loads`;
  - `untrusted`, the filled-in block said where it must hold anything (`consistency.filled`);
  - the construction-volume check's `strength`, which `check()` now takes from its caller (`checked()`). With no caller,
    it reads the script, as before;
  - the build plan's unchecked parts (`build_plan._unheld`).
- **The page:**
  - with no loads, "Will it hold?" offers the editor under "Say what it must hold": "It doesn't say what it must hold
    yet: add a scenario below, or tell me…";
  - an editor with none of its script's cases says "Its script doesn't say what it must hold: add a scenario." Once a
    row is added on the page, it says "…: save yours to keep them.", never "As its script says them". The page walk
    found that last one: Add a scenario on the empty editor turned its words to the script's.

**Tests:** 12 in tests/test_scenarios_no_loads.py, on a synthetic lidless plywood bin.
- **Pinned:** an added case makes the part say it has loads, opens its studies, counts in the build plan, and its check
  runs on the case. The card then asks for a check, not for loads.
- **Also:**
  - the filled-in block is said once the part has a case;
  - a script's own `loads()` still counts;
  - an edit whose case the design dropped still counts.
- **The page:** the no-loads view shows the editor, the empty editor's words, a row added there not read as the
  script's, and the editor wired either way.
- **test_scenarios.py:** its editor test of a script's own rows now gives the row a script's shape (`of` and
  `source: "script"`, as `scenarios.get` sends). The test was wrong: with no source, its row now reads as one added on
  the page.

**The page walk** (8016, a scratch copy of the camper sample, the cargo box; the demo entry has the steps):
1. "Will it hold?" with no loads shows the editor.
2. Add a scenario: "save yours to keep them".
3. "Two people lying on the mattress, 400 lb × 2", saved as v15: `p.loads` true, the card reads "Not checked yet:
   check it when it looks right.", and Check it holds shows.
4. The check ran: "not trusted: a solid with more in it than its pieces". The cargo box is still built as one block, so
   CALI-96's warning now reaches a part whose case was added.
5. Back to its script's: no loads again, and the editor's empty words.

**The full suite failed once, on my files:** I'd put the walk's screenshots in pm/demo, where the log guard takes only
.md entries. The guard was right. They're out, and pm/demo has a text entry instead.

**Mutants (10),** all caught:
1. an added case never counts
2. added cases only (an edit whose case was dropped not counted)
3. the script's loads() never counts
4. p.loads the script's only
5. untrusted the script's only
6. filled the script's only
7. the volume check the script's only
8. the build plan the script's only
9. no editor with no loads
10. the empty editor says as its script
