#!/bin/bash
cd "$(dirname "$0")/../../.."
for f in "$@"; do
  n=$(python3 -c "import json,sys;print(json.load(open('$f'))['name'])")
  [ -f data/eval-pd/tune3/runs/$n/summary.csv ] && grep -q complete data/eval-pd/tune3/runs/$n/run.json && continue
  echo "=== $n start $(date +%H:%M:%S)"
  .venv/bin/python data/eval-pd/tune3/sweep3.py "$f" 2>&1 | grep -v "^INFO\|HTTP Request"
  echo "=== $n end $(date +%H:%M:%S)"
done
