### 2026-11-09 · Make it better, as the mockup has it (CALI-100 #92, the page)
1. Open a part whose walls are too thin for the check. *Will it work?* ends with **Make it better**: "Make the … walls
   N mm so the check can see them", with **Try it**, then "Carve the … where it isn't working", its button greyed out,
   and the line under it says it waits for a check it can trust.
2. On a part that holds, **Carve it** starts the carve from the card, and afterwards **Use it** takes the step.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_make_it_better.py`.
5. On a part whose check fails because it's too coarse to see its walls, the offer says where the thinnest spot is and what to do about it; Carve is off and says why.
