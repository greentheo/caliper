### 2026-11-15 · CALI-188 (#299) · #305's review: a version restore is read only as the whole message; a named part first; the walk hardened

reviewer-2's review and the foreman's list on #305.

- **1. A version restore is read by its words only as the whole message:** a verb (roll … back, revert, go back, back, restore), the version, optionally a part's name ("of the inside corner fillets", "roll the inside corner fillets back") and "please". That's `_REVERT_TO.fullmatch`.
  - **Anything else goes the ordinary way:** "don't go back to v3, make it 2 in taller", "I don't want to roll it back to v3", "restore v3's width but keep the new height", "make it taller, and if that fails, go back to v3". A question is excluded the same way: a trailing "?" never matches.
- **2. A part named in the words beats the selected part.** "go back to v1 of the inside corner fillets" with the stool selected restores the fillets. Words that don't name a part exactly, or name two, go the ordinary way.
- **3. The three phrasing mutants are dead:**
  - "remove v3" isn't a verb it takes;
  - "roll it back to v3?" isn't the whole phrase;
  - "restore the 2 rails" isn't either.
  - **A bare number** ("back to 3", "go back to 3") is read only as the whole message, and only where that version is there. "go back to 12" goes the ordinary way.
- **4. The walk is hardened.** Where a version's history line is missing, a version whose script is an earlier one's counts as its restore (`chat._restores`). With v6's line gone, the walk still goes v7 → v6 → v3, never v5.
  - **A refine that wrote an earlier script again** is still a refine, since its line says so. `test_promote`'s carriage, revised back to its v1 script, had read as a restore and rolled back to nothing. That was the code's fault, and it's pinned now.
- **5. Versions ▸ scrolls:** `.pmenu` has `max-height: calc(100vh - 16px); overflow-y: auto`.
- **6. The foreman's call, on the reviewer's question:** a plain "roll it back" steps back along the part's lineage; it isn't "undo my last action". After going back to v3 (saved as v8), it goes to v2, and says so: "↩ rolled **step_stool** back to v2, the one before v3 (saved as v9). To go back to where you were, say "go back to v7"."
  - **"Where you were"** is the version before the run of restores, so it stays v7 through several roll-backs in a row.
  - Theo can overrule this.

**Tests:** `tests/test_roll_back_to.py`, 33 cases:
- the four messages, plus the three mutants' phrasings and "go back to 12";
- a bare number, three ways;
- the named part;
- the missing line;
- the lineage reply, through three roll-backs;
- the menu's scroll;
- words that name a part with words that don't;
- a refine of an earlier script.
- **Mutants:** 10. 9 are caught, the refine-as-restore one included. The ninth, "a question acts", showed the `?` guard was dead, since the whole-message match already refuses it, so the guard is gone.
- **Around run:** 117 files. One failure, `test_promote`'s roll-back, was the code's fault, as above. After the fix, the 34 files that roll back, restore or read history pass.
