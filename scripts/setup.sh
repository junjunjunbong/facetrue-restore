#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--comfy" ) ]]; then
  printf '%s\n' 'Usage: bash scripts/setup.sh [--comfy]' >&2
  exit 2
fi
requirements=( -r requirements-lock.txt )
if [[ "${1:-}" == "--comfy" ]]; then
  requirements+=( -r requirements-comfy-lock.txt )
fi
if command -v uv >/dev/null 2>&1; then
  if [[ ! -x .venv/bin/python ]]; then uv venv --python 3.11 .venv; fi
  uv pip install --python .venv/bin/python "${requirements[@]}"
else
  python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required (or install uv)"'
  if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
  .venv/bin/python -m pip install "${requirements[@]}"
fi
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  printf '%s\n' 'Install FFmpeg: brew install ffmpeg (Mac), or your system package manager.'
fi
printf '%s\n' 'Ready: bash scripts/run.sh'
