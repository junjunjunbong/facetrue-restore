# TakeWeaver

Salvage the usable spans from imperfect AI video takes, and regenerate only the shots that are still missing.

Built for the Comfy **Open Source Higgsfield** challenge — *Open Weights Only* track (no partner nodes, no closed APIs).

## How it works
1. Upload a product photo + short brief → TakeWeaver proposes shots and pass conditions.
2. It generates takes with a local ComfyUI workflow, a local VLM proposes usable spans, you confirm.
3. Only shots with no usable span get regenerated; confirmed spans are stitched into the final cut.

## Stack
- Local ComfyUI (Wan2.2-TI2V-5B first; LTX-2.5 INT8 optional)
- `comfy-sdk` → `comfy-api-proxy` → local ComfyUI
- Qwen3-VL-4B-Instruct (Apache-2.0) as local critic
- FastAPI + simple web UI, FFmpeg/OpenCV for assembly

## Setup
_TBD_

## License
MIT (app code). Model licenses listed in `docs/MODELS.md`.
