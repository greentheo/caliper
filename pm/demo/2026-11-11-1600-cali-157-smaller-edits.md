### 2026-11-11 · Smaller edits (CALI-157 #223 part 3)
1. Offline: `PYTHONPATH=src python -m pytest tests/test_small_edits.py`.
2. With a Claude key: ask for a small change to a part, then read the design's `log.jsonl`: a `revise` entry says how many tries and how long each took.
