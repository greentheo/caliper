### 2026-06-11 · CALI-0 · canonical OCCT env via micromamba (Plan B) + zero-activation workflow
- Anaconda's classic solver stalled 55+ min on cadquery. Switched to standalone **micromamba**
  (osx-arm64), which solved + built the env in <1 min at `/opt/anaconda3/envs/caliper`:
  **cadquery 2.7.0 / occt 7.8.1 / ocp 7.8.1.2 / python 3.11**. Then `pip install -r requirements-pip.txt`.
- cadquery 2.7 dropped the `nptyping` dep → no numpy shim needed (unlike the pip-2.4 scratch venv).
- **`make test` → 47 passed** in the canonical env (auto-resolves the prefix), confirming the code
  works on cadquery 2.7 (not just the 2.4 used for the earlier scratch verification). CLI run → STL ✓.
- Editable-installed the package (`caliper` command) and added `make install`/`make run` targets that
  resolve the env python directly — no shell activation needed. Updated README/environment.yml to
  recommend the micromamba recipe.
- Commits: `e999d31` (micromamba env), `2c64680` (make targets + zero-activation docs).
