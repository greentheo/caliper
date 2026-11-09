### 2026-11-07 · The wording pass (CALI-99 #89)
1. New design: "I want to make a bar stool to hold up to a 250 lb person, sitting." It's named "Bar stool", not
   "I want"; once built, *What is it?* opens with the part's own description.
2. On a printed part whose design aims at print time or weight, *How do I make it?* offers "Carve the … where it
   isn't working, to print less of it: try Carve it."
   Not where the Carve button refuses it: on the bar stool (a copy, v7, failing as drawn) neither is offered, and the
   button says why in the same words.
3. A reply that once showed a traceback shows its last line, with no paths on this machine.
4. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_wording.py`.
