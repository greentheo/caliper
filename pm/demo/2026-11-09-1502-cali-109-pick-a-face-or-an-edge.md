### 2026-11-09 · Pick a face or an edge (CALI-109 #109, slice a)
1. Open a design. In the view bar choose **Edge**, click a part (the first click selects it and works out its edges,
   a few seconds), then click an edge: it goes amber and the chip says what it is.
2. **Face** picks a face. **Part** goes back to picking parts.
3. Type a message: it goes as "About this edge: … (at x, y, z mm in the script's coordinates): …".
4. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_features.py`.
