### 2026-11-07 · The questions read your shop (CALI-124 #145)
1. With a printer in your shop (Shop → printer, 256 mm): start a design that's printed. No question asks your bed
   size; one says "Your printer: 256 × 256 × 256 mm build volume, PLA, PETG. If this one's to be made on something
   else, say what."
2. With no shop yet: answer the bed-size question "256 x 256 x 256 mm, PETG". Under *Requirements*: "Add a 256 × 256 ×
   256 mm printer (PETG) to your shop?" — **Add it** writes it to your shop (Shop shows it); **No** leaves it.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_shop_questions.py`.
