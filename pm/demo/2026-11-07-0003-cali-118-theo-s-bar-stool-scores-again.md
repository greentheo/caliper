### 2026-11-07 · Theo's bar stool scores again (CALI-118 #126)
1. Open a design with a printed cone (the bar stool): its card says "I left out 1 stray face from the CAD's meshing
   (at z …): it enclosed nothing and weighs nothing." Its weight, balance, scorecard and build package all work.
2. A part whose shape really isn't closed says "not checked: its shape isn't closed near z … mm" for its weight and
   its strength, and nothing throws.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_stray_faces.py`.
