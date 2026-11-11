### 2026-11-11 · A first build says what it's doing, and keeps saying it (CALI-154 #218)
1. Offline: `PYTHONPATH=src python -m pytest tests/test_first_build_progress.py`.
2. With a Claude key: press **Build it** on a new design. The bubble names each step, how long the build has been running, and which try authoring is on. Reload or switch designs and come back: it carries on with the right time.
