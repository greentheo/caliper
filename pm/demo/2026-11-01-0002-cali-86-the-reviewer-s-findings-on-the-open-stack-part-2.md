### 2026-11-01 · The reviewer's findings on the open stack, part 2 (CALI-86 #62, findings 8–13)
1. **Carve a plywood top on printed sides:** the chart, the Studies line and the reply say "% of the printed
   part carved away", and the share matches the filament saved.
2. **Check a printed part holds:** *Will it work?* says "about N times over (printed parts are a rough model…)".
3. **Without whittle installed, put a T-rex on a part that has loads():** the reply says it couldn't check it
   still holds, with no ✓.
4. **Record a test that broke at 150 lb on the stool** (it must hold 400): the card's line is red and says so. A
   sag 15× the prediction is amber.
5. `curl -X POST localhost:8016/api/samples/%2E%2E`: 404, and nothing is copied.
6. **Open the camper sample:** *Will it work?* carries "A prediction, not a certificate …".
7. Offline: `PYTHONPATH=src python -m pytest tests/test_mixed.py tests/test_printed_strength.py
   tests/test_pictures.py tests/test_trials.py tests/test_samples.py -rs`.
