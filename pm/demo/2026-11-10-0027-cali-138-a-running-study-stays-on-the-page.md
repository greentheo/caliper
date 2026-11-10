### 2026-11-10 · A running study stays on the page (CALI-138 #178)
1. Start **Check it holds**, reload or go to another design and back: the line is still there and the button is off.
2. A second click, or a second tab, says it's already running.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_running.py`.
