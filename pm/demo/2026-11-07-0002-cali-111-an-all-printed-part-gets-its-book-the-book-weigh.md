### 2026-11-07 · An all-printed part gets its book; the book weighs what the card does (CALI-111 #112)
1. Open a design that's all printed (a tube, a printed box) and press **Make the build package**: it's made, and its
   cut list says "Nothing to cut: it's all printed."
2. On a design with a printed part and plywood: the build book's scorecard and the design card give the same total
   weight. A card scored before this reads "score it again" until it's re-scored.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_printed_release.py`.
