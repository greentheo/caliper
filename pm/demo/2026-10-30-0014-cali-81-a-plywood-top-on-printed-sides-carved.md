### 2026-10-30 · A plywood top on printed sides, carved (CALI-81 #53, CALI-82 #54)
1. Needs whittle at `65e7e59` (greentheo/whittle#4; `make tools`, or merge and pull your checkout). Without it the
   two materials are analysed at the printed stiffness, and it says so.
2. Ask for "a step stool with a 3/4 in plywood top and 3D printed sides, PETG at 40%". The part lists the top as a
   sheet and `"kind": "printed", "rest": true`: *What do I buy?* has the plywood and the filament; with a printer in
   **Shop**, *How do I make it?* prints only the sides.
3. **Check it holds:** the top as a plate or (on two sides) a beam, in plywood; the sides as printed PETG.
4. **Carve it** (a few minutes): the chart of steps down to where the sides stop holding. Click a step to see it,
   **Carve it like this** to make it the shape, and the strength check runs again. "carve the sides" does it from
   the chat.
5. Offline: `python -m pytest tests/test_printed_strength.py tests/test_mixed.py`.
