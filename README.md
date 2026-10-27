# FaceTrue Restore

Restore old family video on your own PC with open weights, and keep each face looking like the real person by giving the model a separate photo of them.

**Example:** a blurry 1980s VHS clip of your grandmother (black and white is fine) + one photo of her from the same years → a sharp HD clip whose face matches the photo, plus a side-by-side comparison video.

Built for the Comfy **Open Source Higgsfield** challenge, *Open Weights Only* track (no partner nodes, no closed APIs).

## Features
- **Three-way comparison (main feature):** original / restore without the photo / restore with the photo, at the same frame, so you can see what the photo changes.
- **Click a face, drop a photo:** the app builds the reference canvas for you (gray, output-size, face pasted at its location).
- **Chunking and stitching:** 97-frame windows with 17-frame overlap; the reference is re-placed per chunk as the face moves.
- **Deinterlace** for VHS sources.
- **Period-appropriate negative prompt preset.**
- **Wipe comparison MP4 export.**

MVP limits: one person, 4–10 second clips, fixed framing first.

## Models and licenses
| Model | Use | License |
|---|---|---|
| [LTX-2.5 22B](https://huggingface.co/Lightricks/LTX-2.5) | Core video model | LTX-2.x Community License |
| [LTX-2.5 22B IC-LoRA Restore](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore) | Restoration, colorization, reference-guided faces | LTX-2.x Community License |
| Gemma text encoder (INT8, low-VRAM path) | Prompt encoding | See upstream license |

App code only. No model weights are included in this repo.

## Stack
- ComfyUI on an RTX 5090 (32 GB), low-VRAM path: INT8 transformer + INT8 Gemma + offload (64 GB+ RAM recommended)
- `comfy-sdk` → `comfy-api-proxy` (127.0.0.1:8189) → ComfyUI (8188)
- FastAPI + thin web UI, FFmpeg/OpenCV

## Setup
_TBD_

## Limits
Restoration is generative: colors and fine details are reconstructed, not recovered. Demo clips that were artificially degraded for testing are labeled as such.

## License
MIT (app code). Models are under their own licenses (see above).
