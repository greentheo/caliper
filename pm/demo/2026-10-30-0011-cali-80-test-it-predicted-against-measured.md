### 2026-10-30 · Test it: predicted against measured (CALI-80 #48)
1. Click the stool → **Will it work? → the numbers → Test it**. It says where to put the load, what to measure
   the sag with (a dial indicator: under Dad the top should sag only 0.003–0.005 in), and that it should break at
   about 1,240 lb. The chart is the predicted band, with a red line where it should break.
2. Record a step: **load** 200, **sag** 0.004, **Record**. The point lands on the chart and *Will it work?* reads
   "Tested: it held 200 lb, sagging 0.004 in (we predicted …)". Tick **it broke** on the last one.
3. Offline: `python -m pytest tests/test_trials.py`.
