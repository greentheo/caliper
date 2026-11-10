### 2026-11-11 · A safety is cut toward safe before anything compares it (CALI-152 #213)
1. Offline: `PYTHONPATH=src python -m pytest tests/test_cut_before_compare.py`. The plate check at a true 1.995 against 2 stores 1.99 (it was 2.0). Tipping at 1.995 stores 1.99. No producer rounds a safety.
