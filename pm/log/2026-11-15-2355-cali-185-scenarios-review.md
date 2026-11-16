### 2026-11-15 · CALI-185 (#296) · #312 review: a version carries its loads; edited loads follow the shape or say so; the floor kept; the scorecard says one turned off

reviewer-2's review of #312 found four places where a check would run on loads other than the page or the reply said (Rule 6). The foreman made all four must-fix. Five of the small asks came cheap and are in too.

1. **A version carries its loads.**
   - **The bug:** "roll it back" after a load edit put back the same script and kept the edit, while saying it had rolled back.
   - **Now,** each version writes `versions/vNNN/scenarios.yaml` beside its script, absent meaning the script's.
   - **Restoring:** `store.restore` ("roll it back", "go back to v3", and history's "Go back to this") puts that version's loads back, or the script's.
   - **The reply says so:** "↩ rolled **stool** back to v1 (saved as v3): its loads are the script's again (undone: EN 14183, edited: 100 kg (the standard is 150 kg))", or "its loads are as they were at v2".
2. **Edited loads follow the shape, or it says so.**
   - **The bug:** a box the person never moved stayed at the old shape's place after a revision, past the step's back edge, or under a raised top.
   - **Rows never moved:** a row is marked `moved` at save, against its script's box of the same name (a standard's own name). One never moved takes its script's box now, by name, wherever the shape went.
   - **Rows moved:** they stay where the person put them. When the script changes after the edit (`script_sha`), it's said: "Its shape changed since you edited its loads: 'stepping on the front edge' doesn't touch it any more (44 mm off its nearest surface). Check it, and move it under Scenarios and supports, or put it back to its script's there."
   - **Where it's said:** at every chat exit that writes a part (a revision, the several-part revision, a shared number, a roll-back), every part with edited loads; in the number setter's reply; on the "Will it work?" card.
   - **The check still refuses** a box that pushes on thin air.
3. **The floor beside another support is kept,** with its own box (`parse_held` reads a `floor` row as the floor). It had been dropped, while the page still showed it.
4. **The scorecard's strength line says a scenario turned off:** "of the loads left on: its rating (EN 14183, 150 kg) is turned off", beside any unresolved note. Before, it gave the weakest load of the cases left on with no note.

**Small asks:**
- **A standard's numbers** come from the script or the stored edit, by name, never from the request.
- **"Back to its script's" with nothing edited** writes nothing.
- **The routes refuse in words** while a job works on the part (`_refuse_while_busy`, as #302 settled).
- **A mirror's loads are its source's:** "stool_m mirrors stool: edit stool's loads, which its mirror is checked to".
- **History says what changed:** "loads: stepping on the front edge: 250 → 260 lb; its rating (EN 14183, 150 kg): off".

**Found while pinning these (the code's fault):** my first placement of the card's drift line broke the card's `if runs: … elif …` chain. A checked part with nothing left behind would have read "Not checked yet: check it when it looks right." It's moved after the chain, and pinned.

**Not in this PR** (said on the PR):
- a load-only version still marks patterns and cut plans out of date;
- the designer's `loads_land` rule, the CALI-94 edge rule and pictures still read the script's loads.

**Tests:** `tests/test_scenarios.py`, 36 now:
- restore across an edit, and both roll-back words;
- unmoved rows following a taller script;
- a moved row named, in `drift`, in the number setter's reply, at a turn's end and on the card;
- the floor kept;
- the scorecard's note;
- a forged standard;
- a no-op clear;
- the history words;
- a mirror refused;
- the routes refusing while busy.

**Mutants:** 18 on the rework, all caught. Two survived the first pass (the turn's note and the card's line) until a turn and the card were pinned; they're what found the turn's early exits and the card's chain.
