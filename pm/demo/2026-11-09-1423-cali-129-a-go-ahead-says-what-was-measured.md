### 2026-11-09 · A go-ahead says what was measured (CALI-129 #158)
1. No live call here, by the rule until the walkthrough. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_fix_rule_measured.py`.
2. The first test shows the prompt: how thin the wall is, x/y/z in the script's own mm, and what the rule needs.
3. Live, later: on a part with a failing `min_wall` rule, say "have a go". The revision's change should be at that spot.
