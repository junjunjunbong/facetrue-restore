# GPU setup, model files and licenses

Sources below were inspected on 2026-10-27. These are source-contract pins and published model recommendations. They are **not a recorded successful RTX 5090 environment**. Complete [GPU_PREFLIGHT.md](GPU_PREFLIGHT.md) before describing the configuration as tested.

## 1. ComfyUI on the GPU PC

Use the GPU PC's existing supported NVIDIA driver and a Python environment with CUDA-enabled PyTorch. The inspected [ComfyUI installation instructions](https://github.com/Comfy-Org/ComfyUI/blob/426f5eea52a7ece1dd599fff4cb6cd1f352ddd24/README.md#manual-install-windows-linux) recommend current stable CUDA 13.0 PyTorch for NVIDIA. Python 3.12 is a reasonable starting point for the LTX custom-node dependencies. Do not install this CUDA stack into the Mac app environment.

For a **new** manual Linux checkout:

```bash
git clone https://github.com/Comfy-Org/ComfyUI.git
cd ComfyUI
git checkout 426f5eea52a7ece1dd599fff4cb6cd1f352ddd24
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130
python -m pip install -r requirements.txt
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git custom_nodes/ComfyUI-LTXVideo
git -C custom_nodes/ComfyUI-LTXVideo checkout 220e1d45aa0469f518e982102fca4dca92a61862
python -m pip install -r custom_nodes/ComfyUI-LTXVideo/requirements.txt
```

On Windows, create the environment with `py -3.12 -m venv .venv` and use `.\.venv\Scripts\python.exe` for the Python commands, or use the corresponding Python executable in an existing portable ComfyUI installation. Git commands and model destinations remain equivalent. Read [the LTX manual-install instructions](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui#alternative-manual-installation) for the portable environment's dependency command.

The source pins are:

| Repository | Inspected revision |
|---|---|
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI/tree/426f5eea52a7ece1dd599fff4cb6cd1f352ddd24) | `426f5eea52a7ece1dd599fff4cb6cd1f352ddd24` |
| [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo/tree/220e1d45aa0469f518e982102fca4dca92a61862) | `220e1d45aa0469f518e982102fca4dca92a61862` |

Install both repositories' requirements into the **same ComfyUI Python environment**. Some upstream dependencies are version ranges rather than a full lockfile. Save the actual `pip freeze`, Python, PyTorch, CUDA and driver versions with the GPU preflight results.

No separate GGUF, Kijai or Q8 custom-node pack is referenced by this graph. Its ConvRot INT8 files use core `UNETLoader` and `CLIPLoader`; the additional restoration/guide/sampler nodes come from `ComfyUI-LTXVideo`. The current core video nodes, including the `SaveVideo` DynamicCombo inputs, are needed. [Graph contract and adaptations](../workflows/PROVENANCE.md).

## 2. Download four restoration files

First review the access conditions and license on both [LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5) and [Restore IC-LoRA](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore). The pages require the account holder to accept gated access conditions. This repository does not perform that acceptance. Use your existing approved Hugging Face access locally; never put a token in this repository or a copied command transcript.

| Hugging Face repository / relative file | Destination relative to `ComfyUI/` |
|---|---|
| `Lightricks/LTX-2.5` / `diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | `models/diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` |
| `Lightricks/LTX-2.5` / `text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | `models/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` |
| `Lightricks/LTX-2.5` / `vae/ltx-2.5-video-vae-conv-bf16.safetensors` | `models/vae/ltx-2.5-video-vae-conv-bf16.safetensors` |
| `Lightricks/LTX-2.5-22b-IC-LoRA-Restore` / `ltx-2.5-22b-ic-lora-restore-1.0.safetensors` | `models/loras/ltx-2.5-22b-ic-lora-restore-1.0.safetensors` |

These filenames and destinations follow [the official lower-VRAM file list](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui#lower-vram-model-files) and [Restore's card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore). The gated file bytes were not downloaded during development; their local hashes and revisions must be recorded during installation.

After the account holder has granted access, the following commands can be run **inside `ComfyUI/`** using the official Hugging Face CLI:

```bash
hf download Lightricks/LTX-2.5 \
  diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors \
  text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors \
  vae/ltx-2.5-video-vae-conv-bf16.safetensors \
  --local-dir models

hf download Lightricks/LTX-2.5-22b-IC-LoRA-Restore \
  ltx-2.5-22b-ic-lora-restore-1.0.safetensors \
  --local-dir models/loras
```

No audio VAE, prompt-enhancement model, spatial upscaler, hosted Gemma API, or partner node is part of the shipped graph. Source audio is preserved by the app's FFmpeg pipeline rather than generated by Restore.

Restart ComfyUI after installation. From the ComfyUI environment, a launch configuration to evaluate is:

```bash
python main.py --listen 0.0.0.0 --port 8188 --lowvram
```

Use the GPU PC's trusted LAN/VPN address in the Mac's `COMFYUI_URL`. Keep the Mac proxy on `127.0.0.1:8189`. Offload and `--lowvram` can trade speed for memory; record the actual flags and measurements. No tested peak-memory or speed figure is currently available.

## 3. Configuration contract

The graph uses 8 distilled steps, CFG 1, 960×544 spatial tiles, no photo-guide streaming and application-controlled temporal windows. The app defaults to 1280×736 at 24 fps. The [Restore card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore) is the basis for the restoration configuration; [PROVENANCE.md](../workflows/PROVENANCE.md) lists every graph adaptation.

The following environment variables override the relative model filenames when a local installation uses subfolders. They do not download models:

```dotenv
FACETRUE_TRANSFORMER=ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors
FACETRUE_TEXT_ENCODER=gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors
FACETRUE_VIDEO_VAE=ltx-2.5-video-vae-conv-bf16.safetensors
FACETRUE_RESTORE_LORA=ltx-2.5-22b-ic-lora-restore-1.0.safetensors
```

## 4. License record

| Material | Verified published terms | Remaining qualification |
|---|---|---|
| App-owned code | [MIT](../LICENSE), copyright 2026 Junwon Seo | Does not cover third-party material |
| LTX-2.5 transformer and Conv VAE | [LTX-2.x Community License](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x), linked by the [model card](https://huggingface.co/Lightricks/LTX-2.5) | Read the complete use, redistribution and commercial terms; these are open weights, not an MIT weight release |
| Restore IC-LoRA | [LTX-2.x Community License](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x), declared by the [adapter card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore) | Gated access conditions must be reviewed separately |
| Google Gemma 4 12B base | [Google's official model card](https://huggingface.co/google/gemma-4-12B-it) declares Apache-2.0 | This app loads Lightricks' with-projection INT8 package, not Google's original file |
| Lightricks Gemma 4 projection/INT8 package | Distributed in [LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5) | Exact packaged-component notices/terms: **확인 필요**; do not relabel the whole bundle Apache-2.0 based only on the Google base |
| Adapted API workflow | Retains [Lightricks' upstream license](../workflows/LICENSE.upstream.txt) and [adaptation notice](../workflows/PROVENANCE.md) | The inspected upstream repository license is the LTX-2 Community License dated January 5, 2026; it is separate from the later model-license text |
| UI OpenCV Haar face classifier | [Classifier header](https://github.com/opencv/opencv/blob/4.x/data/haarcascades/haarcascade_frontalface_default.xml) carries Intel's Open Source Computer Vision Library license | Preserve the upstream package/file notices; it proposes crops and is not an identity model |
| Evaluation YuNet 2023mar | [Model-directory MIT license](https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE) | Optional local evaluation download |
| Evaluation SFace 2021dec | [Model-directory Apache-2.0 license](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/LICENSE) | Exact training-data provenance: **확인 필요**; [upstream #313](https://github.com/opencv/opencv_zoo/issues/313), [#318](https://github.com/opencv/opencv_zoo/issues/318) |
| Python Comfy SDK / local API proxy | MIT declared in the respective [SDK](https://github.com/Comfy-Org/comfy-python-sdk/blob/main/pyproject.toml) and [proxy](https://github.com/Comfy-Org/comfy-api-proxy/blob/main/pyproject.toml) package metadata | Client requirements pin `comfy-sdk==0.5.0` and `comfy-api-proxy==0.1.6`; these are code dependencies, not generative models |

The LTX-2.x license is dated August 11, 2026 and contains conditions for entities with annual revenue of at least $10 million, along with use and redistribution terms. This project does not replace those terms with an unrestricted-commercial-use claim. [Full controlling text](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x).

Dependency packages and external servers retain their own licenses. The app's MIT license does not relicense ComfyUI, its custom nodes, the SDK/proxy, FFmpeg, OpenCV, or their bundled components. This repository contains no model weights. See [EVALUATION.md](EVALUATION.md) for the optional evaluation models' exact hashes and download procedure.
