### 2026-11-09 · The pick reaches the designer (CALI-109 #109, slices b and c)
1. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_features.py`. A stubbed designer that fillets the wrong edge gets "✗ The edge you picked is still there".
2. Live, after #155 and Theo's word: pick the concave cone-and-flange edge, say "fillet this 1/2 in".
