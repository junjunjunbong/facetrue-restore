#!/usr/bin/env python3
"""Read-only runtime checks. Proxy health alone never means the GPU is ready."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.config import Settings
from app.workflow import LOCAL_NODE_TYPES, ModelFiles


def inspect(settings: Settings, require_gpu: bool) -> dict:
    checks = []

    def record(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    for command in (settings.ffmpeg, settings.ffprobe):
        record(command, shutil.which(command), "Executable found" if shutil.which(command) else "Install FFmpeg")
    record("mode", True, settings.mode)
    if settings.mode == "mock" and not require_gpu:
        return {"ok": all(c["ok"] for c in checks), "gpu_checked": False,
                "notice": "Mock mode. No inference or quality validation has run.", "checks": checks}
    for package in ("comfy-sdk", "comfy-api-proxy"):
        try:
            record(package, True, importlib.metadata.version(package))
        except importlib.metadata.PackageNotFoundError:
            record(package, False, "Install requirements-comfy.txt in this app environment")
    models = ModelFiles.from_env()
    with httpx.Client(timeout=10, trust_env=False) as client:
        try:
            response = client.get(str(settings.comfy_proxy_url).rstrip("/") + "/api/v2/health")
            response.raise_for_status()
            record("proxy", True, "HTTP health only; does not verify the GPU")
        except httpx.HTTPError as error:
            record("proxy", False, type(error).__name__ + ": run bash scripts/run_proxy.sh")
        root = str(settings.comfyui_url).rstrip("/")
        try:
            response = client.get(root + "/system_stats")
            response.raise_for_status()
            devices = response.json().get("devices", [])
            record("ComfyUI devices", bool(devices), [
                {key: d.get(key) for key in ("name", "type", "vram_total", "vram_free")} for d in devices])
            response = client.get(root + "/object_info")
            response.raise_for_status()
            nodes = response.json()
            missing = sorted(LOCAL_NODE_TYPES - nodes.keys())
            record("workflow node classes", not missing, {"missing": missing})
            for node, input_name, name in (("UNETLoader", "unet_name", models.transformer),
                                          ("CLIPLoader", "clip_name", models.text_encoder),
                                          ("VAELoader", "vae_name", models.video_vae),
                                          ("LTXICLoRALoaderModelOnly", "lora_name", models.restore_lora)):
                definition = nodes.get(node, {}).get("input", {}).get("required", {}).get(input_name, [])
                available = definition[0] if definition and isinstance(definition[0], list) else []
                record(name, name in available, "Available to loader" if name in available else "Missing or node schema changed")
        except (httpx.HTTPError, ValueError) as error:
            record("ComfyUI", False, type(error).__name__ + ": configure COMFYUI_URL for the GPU PC and start ComfyUI")
    return {"ok": all(c["ok"] for c in checks), "gpu_checked": True, "inference_verified": False,
            "notice": "Read-only connectivity and model discovery; run 49/97-frame inference separately.", "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-gpu", action="store_true")
    args = parser.parse_args()
    result = inspect(Settings(), args.require_gpu)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
