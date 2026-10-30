#!/bin/bash
cd /Users/junwon/Hackathon/facetrue-restore
while pgrep -f "sweep4.py data/eval-pd/tune4/cfg/a4.json" > /dev/null; do sleep 10; done
for c in c1 c2; do .venv/bin/python data/eval-pd/tune4/sweep4.py data/eval-pd/tune4/cfg/$c.json > data/eval-pd/tune4/$c.log 2>&1; done
