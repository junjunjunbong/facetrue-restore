#!/bin/bash
cd "$(dirname "$0")/../../.."
bash data/eval-pd/tune4/runq.sh "$@" > data/eval-pd/tune4/runq.log 2>&1
