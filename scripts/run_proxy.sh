#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "Create .venv and install requirements.txt and requirements-comfy.txt first." >&2
  exit 1
fi
exec .venv/bin/python - <<'PY'
import os
import shutil
from urllib.parse import urlsplit

from app.config import Settings
from app.comfy_backend import _loopback_proxy_url

settings = Settings()
proxy = urlsplit(_loopback_proxy_url(settings.comfy_proxy_url))
executable = shutil.which("comfy-api-proxy", path=str(__import__('pathlib').Path('.venv/bin').resolve()))
if executable is None:
    raise SystemExit("Install requirements-comfy.txt before starting the proxy.")
command = [executable, "run", "--comfyui", str(settings.comfyui_url).rstrip("/"),
           "--host", proxy.hostname, "--port", str(proxy.port or (443 if proxy.scheme == 'https' else 80)),
           "--max-upload-mb", str(settings.upload_limit_mb),
           "--state-dir", str(settings.data_dir / "proxy")]
if proxy.scheme != "http":
    raise SystemExit("This launch script serves HTTP. Use http://127.0.0.1:8189 for COMFY_PROXY_URL.")
# Inputs travel to the remote ComfyUI. Model-directory upload is not enabled.
os.execv(executable, command)
PY
