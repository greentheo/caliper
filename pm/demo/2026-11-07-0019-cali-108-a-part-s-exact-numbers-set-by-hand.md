### 2026-11-07 · A part's exact numbers, set by hand (CALI-108 #108, the backend)
1. `curl localhost:8016/api/designs/<slug>/parts/<part>/params`: each number in plain words, with its unit and range.
2. `curl -X POST -H 'content-type: application/json' -d '{"name": "wall_t", "value": 5, "unit": "mm"}'
   localhost:8016/api/designs/<slug>/parts/<part>/params`: a new version, its script's `wall_t` line now `5.0` (the
   comment kept), its history "set wall_t to 5 mm by hand", rebuilt and measured, no Claude call. A value outside its
   range is refused with the range. The panel's UI comes after Theo's look at the mockup.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_params.py`.
