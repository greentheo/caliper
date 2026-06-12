#!/usr/bin/env bash
# review.sh — the reviewing-agent guard to run before a commit.
# pytest (regression) + ruff (lint) + a diff summary so changes are reviewed, not rubber-stamped.
set -euo pipefail
cd "$(dirname "$0")/.."

resolve_py() {
  if [[ -n "${CALIPER_PY:-}" ]]; then echo "$CALIPER_PY"; return; fi
  for p in "/opt/anaconda3/envs/caliper/bin/python" "$HOME/anaconda3/envs/caliper/bin/python" "$HOME/miniforge3/envs/caliper/bin/python"; do
    [[ -x "$p" ]] && { echo "$p"; return; }
  done
  command -v python
}
PY="$(resolve_py)"

echo "── 1/3 tests ──"
bash nightshift/hooks/regression_guard.sh

echo; echo "── 2/3 lint (ruff, non-blocking) ──"
"$PY" -m ruff check src tests 2>/dev/null || echo "(ruff not installed or found issues — review above)"

echo; echo "── 3/3 diff summary ──"
git diff --stat
echo; echo "Review complete. If green and reviewed, commit referencing the CALI-N task."
