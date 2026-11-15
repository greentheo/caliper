### 2026-11-14 · CALI-184 (#295) · #303's review: ⚠ piece by piece; a plate row's Use is its own piece's; a run as the print isn't trusted

The reviewer's review and the foreman's list on #303.

- **1. The ⚠ is decided piece by piece** (`chat._made_otherwise`).
  - **What counts:** a piece, by name, whose kind or material changed ("the panel was a softwood plywood sheet and is now a PLA (printed) print"), or sheets that went while prints came under new names ("6 softwood plywood sheets became 1 PLA (printed) print").
  - **What doesn't:** a piece added or taken away in its own material ("add a shelf", "take the shelf out").
  - **It's silenced only where the request names what it became:** printing or its material for a print, the sheet's material for a sheet. "From 5/8 in plywood", "keep it wooden, just thinner", "use less material" and "it's fine as plywood" all read ⚠ on a panel rebuilt as a print. "Print it in PLA" and "make it printed" don't.
  - **On a ✗ reply,** `_say_made` keeps the ✗ and adds the words. It puts ⚠ only over a ✓ or a "!".
- **2. A plate row's Use is its own piece's number.** `load_study._thickness_names` tells which `PARAMS` number each sheet's thickness comes from, for certain:
  - each read number equal to a thickness is moved by 1 mm in a copy of the script;
  - it names the sheets whose thickness follows it, and only those;
  - a coincidence (a lip of 12.7) moves no sheet;
  - two numbers that both move one sheet name neither.

  How it's used:
  - `sheet.pieces` maps each sheet to its number. `sheet.param` (a Lighten's estimate, which scales every sheet) is set only where every sheet is one thickness from one number.
  - The plate row passes its piece: top_t 12.7 / side_t 19.05 sets `top_t` on the top's row, never `side_t`.
  - Where it can't be told, the Use says it in words: "Make the shelf 3/8 in softwood plywood, not 1/2 in".
- **3. A Lighten run as the print, on a sheet part, isn't trusted** (`lighten.wrong_material`): "Not trusted: it ran as PLA (printed), not as its softwood plywood. Lighten it again."
  - **Where it's set:** `list_runs` marks it.
  - **The steps:** each step's verdict is untrusted (so "Cut these holes" is greyed), and `adopt` refuses it.
  - **The panel** leads with the words.
  - **What isn't marked:** a printed part's run (`made_of` carves it), and a run in the sheet.
  - **On a scratch copy of Theo's step-stool-5,** his v4 run 20261113-172306 reads exactly that; his plywood runs read nothing.

**Tests:** `tests/test_lighten_sheet.py`, 30 tests (15 new), all failing on f97f230 except those that held before:
- the review's six phrases, plus "make it printed";
- the shelf both ways;
- the ✗ words;
- the two-thickness part's numbers (never the lip);
- the plate row's Use;
- Theo's run shape, as not trusted, not adoptable, and untrusted step by step;
- a plywood run and a printed part's run, both trusted;
- the panel's lead;
- sheets gone and a print come under a new name;
- a row's own number before the part's.

The `sheet_param` pin now tells by the sheet following a number, not by a number equalling it.
- **Mutants:** 16, all caught. Two survived until those last two tests were added.
- **Around run:** 125 files pass, the same set as the first round.
