#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
  uv venv --python 3.11 .venv
  uv pip install --python .venv/bin/python -r requirements-dev.txt
else
  python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required (or install uv)"'
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements-dev.txt
fi
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  printf '%s\n' 'Install FFmpeg: brew install ffmpeg (Mac), or your system package manager.'
fi
printf '%s\n' 'Ready: bash scripts/run.sh'
