### 2026-11-01 · A load just above its face pushes on it; one that misses says so in both checks (CALI-84 #58)
1. Open Theo's printed `step-stool` and **Check it holds**. Expect: the adult's foot, 1.2 mm above the recess
   floor, now lands, and the check stops at the child's box instead, in the same words the designer's check uses:
   it's in the air, 2.4 mm from the nearest surface, because the script's lower step is inside the upper body.
   (Measured on the script offline; not yet clicked through in the app.)
2. Offline: `PYTHONPATH=src python -m pytest tests/test_load_lands.py tests/test_load_study.py`.
