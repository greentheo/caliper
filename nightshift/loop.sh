#!/usr/bin/env bash
# loop.sh — one bounded dev iteration (local, on-demand; no cron).
# Mirrors ai-night-shift's night_shift.sh shape: show the queue, run the guard, surface next work.
# A bounded, non-interactive single pass — safe to wrap with a real agent later.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "════════════════════════════════════════════"
echo " Caliper dev loop · $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════════════"

echo; echo "── Board ──"
sed -n '/## 🔨 In Progress/,/## ✅ Done/p' pm/BOARD.md || true

echo; echo "── Regression guard ──"
if bash nightshift/hooks/regression_guard.sh; then
  echo "✅ guard green"
else
  echo "❌ guard red — fix before committing"; exit 1
fi

echo; echo "── Next up (Backlog top) ──"
awk '/## 🧊 Backlog/{f=1;next} /^## /{f=0} f && /^- /{print; exit}' pm/BOARD.md || true
echo; echo "Loop iteration complete."
