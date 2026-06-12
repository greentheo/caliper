#!/usr/bin/env bash
# Regression guard — runs the test suite and fails loudly on any regression.
# Used by `make test` / `make review` and intended to gate any future autonomous loop.
set -euo pipefail
cd "$(dirname "$0")/../.."

# Resolve the caliper python. Override with CALIPER_PY if your env lives elsewhere.
resolve_py() {
  if [[ -n "${CALIPER_PY:-}" ]]; then echo "$CALIPER_PY"; return; fi
  for p in \
    "/opt/anaconda3/envs/caliper/bin/python" \
    "$HOME/anaconda3/envs/caliper/bin/python" \
    "$HOME/miniforge3/envs/caliper/bin/python"; do
    [[ -x "$p" ]] && { echo "$p"; return; }
  done
  command -v python
}
PY="$(resolve_py)"
echo "▶ regression guard using: $PY"
"$PY" -m pytest "$@"
