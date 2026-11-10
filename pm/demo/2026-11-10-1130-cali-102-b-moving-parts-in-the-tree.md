### 2026-11-10 · Moving parts in the tree (CALI-102 #94)
1. On a design with several parts, drag a part above or below another: the tree reorders and stays that way after a reload.
2. Drag a part onto another: it sits under it, and the upper part's eye hides both. Nothing else about either part changes.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_tree_moves.py`.
