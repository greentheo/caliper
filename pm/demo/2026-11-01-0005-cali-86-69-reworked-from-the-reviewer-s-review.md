### 2026-11-01 · #69 reworked from the reviewer's review (CALI-86 #62)
1. **A foot at the free end of a wide top on two sides:** the numbers name a narrower width ("… this near its
   free end") and a lower safety than the same foot in the middle.
2. **Break `design.yaml` with a line of your own words, then open the design:** the 500 says "Something went
   wrong on Caliper's side (error …)", and the report has the line and column but none of your words.
3. **Add a hand-written bad line to a trials file, or a NaN to `log.jsonl`:** the page loads, and says a line
   was left out.
4. **Patterns:** the titles read "left: 3/4 in softwood plywood (this is the outside face)", with no box
   character.
5. **The kids' book:** the cut page has the kid an arm's length behind with ear defenders, and the test page
   has the grown-up go first.
6. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_beam_width.py tests/test_errors.py tests/test_trials.py
   tests/test_samples.py tests/test_patterns.py tests/test_studies.py tests/test_kidbook.py`.
