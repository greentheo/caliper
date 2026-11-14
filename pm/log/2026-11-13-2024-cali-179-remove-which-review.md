### 2026-11-13 · CALI-179 (#287) · #288's review: "moved" covers what a part declares; the page sends what was typed; "side" asks which; "don't remove" isn't one

The foreman accepted #288 with one round before it merges.

- **"Moved" covers what a part declares, not only its solid.** `chat._moved` checks the PARAMS numbers and the solid's volume, box and centre, as before. When none of those moved, it now asks `_declares_moved`. That compares the revision's `JOINTS`, and what the declaration probe reads before and after: the pieces (outline, holes, mortises, covers), `loads()`, `BUILD` and `HOLES`.
  - **The probe on a script's text:** `construction.declared_by(script)` reads it before the script is written; `declared()` now calls it.
  - **The headline case:** a mortise cut in `construction()` alone reads "✓ revised", not "!". That's the edit #275 asks for on Theo's step-stool-5.
  - **Code that declares the same pieces** still reads "!".
  - **A probe that can't be read** counts as nothing moving: no ✓ it can't stand behind.
- **The page sends what was typed as its own field.** That's `typed`, beside the chip text in the message and the selected part as scope. `ChatMessage.typed` is passed to `chat.turn(typed=…)`, and every intent match reads it.
  - **A colon anywhere in a piece's name** is the name's.
  - **`bare`** is now only for a client that doesn't send it, and strips one "About the …:", never in a loop. "About the seat: About the legs: …" leaves "About the legs: …".
- **"remove side" with side_left and side_right asks** "Remove which part? side_left, side_right": every part whose name has all the words. With one of them selected, that one.
  - **One part sharing the words, and no underscore or "part":** that's still a feature edit ("remove the fillets"), and goes to the designer.
- **"Don't remove this part, just …" isn't a remove.** "Not", "never", "no need to" and "without" just before the verb all count.

**Tests:** 14 new cases in `tests/test_remove_which.py`, all failing on 4e09558 except the HOLES one, which already held through the solid's volume and is pinned as asked.
- **The new cases:** the five declarations, plus one control; the typed field through the turn, the API route and the page; strip-once; "side"; three negations.
- **One reworked row:** an old client's two contexts strip once.
- **Mutants:** 33, the first round's and this one's, all caught.
- **Around run:** 114 files: the first round's 93, plus every test that reads `construction`. One failed: `test_features`' #177 page test pinned the old `send(said, S.scope, pick, shown);` call. The test was out of date, not the code: the page still sends the pick, now with what was typed. It pins the new call, and that file passes.
