### 2026-10-30 · A filled-in box is caught; a lightening preview says it's one (CALI-83 #55)
1. Open a stool whose shape was built as a block (Theo's `step-stool-2`): *What is it?* says its 3D shape and its
   pieces don't match, "build() is filled in". Say "fix its shape to match its pieces"; the designer rebuilds it
   from its panels.
2. Lighten it and click a step: the bar says **Preview, not cut yet**, and the patterns and cut plan say they're of
   the stool as it is. **Cut these holes**, then make them again: the holes are on them.
3. Offline: `python -m pytest tests/test_consistency.py tests/test_answers.py`.
