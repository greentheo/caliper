### 2026-11-20 · CALI-171 (#266) · The designer of an added part reads its source's comments true, even ones stale from before #267

This closes the last of #266: #267's small ask 1, left open in #271's "Not done".
- Theo's step_stool was sized 16 × 16 × 14 in through Parameters before #267. So its PARAMS still say `"width": 406.4,  # 24 in`, `"height": 406.4,  # 20 in`, `"top_depth": 355.6,  # 11 in`, rails "3 in" and foot_overhang "2 in".
- #267 puts a comment right only when its number is edited, and #271's `follows.told` handed the designer the block as written. The fillet strips' designer would still read a 20 in stool. That was item 2 of #266.

**The change:**
- **`aero.restate(script)`:** every PARAMS comment says its number now, by #267's rule for a lone figure that states the number. A figure that's already the number as written stays ("18 in" on 457.0 isn't made "17.992"). So does another thing's size ("3/4 in plywood's edge band" on 12 mm).
  - It's for what a reader is shown. Nothing is written: Theo's script on disk is unchanged.
- **`follows.told`** shows the designer the restated block (#266's design note: "comments restated").
- **`params._LENGTH_NAME`** adds overhang, lift, inset, setback and spacing.
  - Without it, `foot_overhang`'s "2 in" stayed: #267 rewrites a stale lone figure only where the name says it's a length.
  - In the Parameters panel, a number by those names with no unit in its comment now reads as a length.
- **#267's rule changed by one clause:** a stale lone figure that is already the new number stays as written.

**Before → after, on a read-only scratch copy of step-stool-5** (`follows.told(store, "step_stool")`, no live call; the copy is deleted):
- Before: 24 in, 20 in, 11 in, 2 in, 3 in, 3 in.
- After: 16 in, 16 in, 14 in, 4 in, 6 in, 6 in. The "2 in" lift and the "3/4 in" ply stay. The file on disk is identical.

**Tests:** 1 in `test_follows.py`, on Theo's PARAMS shape. It failed on main. All 6 hand-made mutants are caught:
1. `told` reads the script as written.
2. The already-the-number guard is dropped.
3. `restate` passes the current numbers as the old ones (near figures are reformatted).
4. `restate`'s no-PARAMS guard is dropped.
5. "overhang" is out of `_LENGTH_NAME`.
6. `_STATES` is dropped, so any lone figure is rewritten.

**Not done:** a part revised in the chat still reads its own stale comments. The revise path edits the script by search and replace, so it can't be shown a restated copy. It's put right as each number is edited.
