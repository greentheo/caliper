### 2026-11-20 · CALI-171 (#266) · an added part's designer reads the stool's sizes as they are now

**Open step-stool-5**, pick the inside-corner edge, and ask for the fillet strips again. The designer of the new part is
now shown step_stool's numbers with true comments: 16 in tall, 16 in wide, 14 in deep, 4 in foot overhang, 6 in rails.
That's in place of the 20 / 24 / 11 / 2 / 3 in the script's old comments still say. The script itself isn't changed:
its comments are put right as each number is edited through Parameters, as before.

**Offline:** `python -m pytest tests/test_follows.py -k comments_true`.
