### 2026-11-01 · The reviewer's findings on the open stack, part 1 (CALI-86 #62, findings 1–7)
1. **A wide top on two sides:** draw a 3 ft wide, 1/2 in top on two printed sides 1 ft apart and **Check it holds**.
   The numbers say "… of it carrying the load (BS 8110's effective width …)", and it no longer reads 2.7×.
2. **Carve a part whose top fails** (test_mixed's 1/2 in top, an adult): the Studies page's carve line starts
   "doesn't hold as it is", and isn't green.
3. **Report an error after a failed chat turn:** the report says "a chat turn", never your words, and
   `designs/<design>` wherever a path had the design's name.
4. `caliper sample save --slug <yours>` with no name: refused, and the samples are all still there.
5. **Record a test step:** NaN, a negative or a zero sag are refused. A hand-written NaN line in the trials file
   is skipped, and the panel says so.
6. **Make a build package and open the kids' book:** the cut and screw pages have the grown-up clamping and
   cutting, and you standing back in safety glasses.
7. **Patterns for a part with a picture on its left side:** the picture faces the way it does on the model seen
   from outside, and every page says "this is the outside face".
8. Offline: `PYTHONPATH=src python -m pytest tests/test_beam_width.py tests/test_mixed.py tests/test_errors.py
   tests/test_samples.py tests/test_trials.py tests/test_kidbook.py tests/test_patterns.py -rs`.
