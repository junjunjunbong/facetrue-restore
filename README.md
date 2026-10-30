# FaceTrue Restore

**Compare local restoration of an old family video with and without a separate photograph of the person, using LTX Restore and synchronized original / no-photo / with-photo views.**

The goal is to make the photo's effect inspectable. A reference photo does not guarantee that a generated face is more accurate. Colors and fine details are reconstructed by a generative model.

![Wipe comparison of the same damaged clip restored without and with a reference photo](docs/img/readme_wipe_synthetic.gif)

*Fictional person generated with open models. Same damaged input and seed; only the reference photo differs.*

Built for the [Comfy Open Source Higgsfield challenge](https://comfy.org/open-source-higgsfield/), targeting Open Weights Only and the LTX VFX bonus. The app workflow uses local models and excludes partner/API generation nodes. [Workflow provenance](workflows/PROVENANCE.md).

## What is implemented

| Feature | Behavior |
|---|---|
| Three-way comparison | Original, restoration without a photo, and restoration with a photo use the same source frames and per-window seeds. Exported panels are composed from matching frame indices. |
| Reference canvas | Click the person on the normalized first frame, supply a separate photo, inspect/correct the crop, and create an output-sized gray canvas with the face at the selected location. The photo guide uses `frame_idx=-1`. |
| Short-clip chaining | 97-frame windows with 17-frame overlap; each arm carries its own restored prefix. Final padding is removed and exact frame count is checked. |
| Preprocessing | Optional deinterlacing, fixed fps, aspect-preserving resize and padding. |
| Exports | Labeled side-by-side and moving-wipe MP4s, with original audio where present. Synthetic-test labels can be burned into comparisons. |
| Offline mock | Exercises upload, selection, job execution, comparison and downloads without a GPU. Mock arms copy the input and carry a visible notice. |
| Paired evaluation | Deliberately degrade HQ footage, run no-photo / correct-photo / wrong-photo conditions, and report local face-embedding diagnostics with detection failures and coverage. |

**Validation status:** CPU/mock tests exercise the app and media pipeline. On one RTX 5090 (32GB, ComfyUI `--lowvram`), 49-, 97- and 240-frame jobs completed in comfy mode with the expected frame counts. Measured so far:

- **Speed:** about 72 s per 97-frame window, at 8 steps and 1280×736 (from the app's render records). A 240-frame (10 s) clip with both arms, 3 windows each, plus export took 482 s (about 8 min) end to end.
- **GPU memory:** the sampled whole-device peak was about 31.9-32.1 GB across the pilot runs (`nvidia-smi` polling). This is not an exact model allocation. GPU-PC system RAM was not measured.
- **Photo effect:** see [Pilot results](#pilot-results-small-test). It is a small test with synthetic damage and one seed, not a benchmark.

The full numbers, a second seed, the ablations and the negative results are in the [technical report](docs/TECHNICAL_REPORT.md).

Run the [GPU preflight](docs/GPU_PREFLIGHT.md) on your own hardware before relying on these numbers.

MVP scope: one person, preferably 4-10 seconds, with little camera or face movement. Face tracking, reference relocation between windows, multiple people, and clips beyond ten seconds are not implemented.

## Start on a Mac without a GPU

Use Python 3.11+ or `uv`, FFmpeg/ffprobe, and Git. The setup script creates `.venv` and installs the tested versions in `requirements-lock.txt`. Install FFmpeg with `brew install ffmpeg` if needed.

```bash
git clone https://github.com/junjunjunbong/facetrue-restore.git
cd facetrue-restore
bash scripts/setup.sh
cp -n .env.example .env
bash scripts/run.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The default is `FACETRUE_MODE=mock`. A private checkout requires a GitHub account that has access; the repository owner will make it public when ready to submit.

Run `.venv/bin/python scripts/doctor.py` for read-only local checks. In mock mode it does not contact a GPU.

1. Upload a short video. Enable deinterlacing for an interlaced source.
2. Click the person's face in the first frame and adjust the selection if needed.
3. Drop a separate photograph of the same person. Select the correct photo face and inspect the gray reference canvas.
4. Choose a period preset and seed. Mark a deliberately degraded evaluation input as a synthetic test clip.
5. Run the comparison. Use the shared playback controls or the exported three-way/wipe MP4.
6. Download the comparison and execution manifest together.

The crop preview matters: automatic face detection can fail on old footage. A center-crop fallback is identified as a fallback, and a multi-person photo requires an explicit selection.

## Connect the RTX 5090 PC

The Mac hosts FastAPI, the browser UI, and the local proxy. The separate GPU PC runs ComfyUI. Uploaded media travels to the configured ComfyUI server; use the address of your own trusted PC.

The request path is **FastAPI → `comfy-sdk` → `comfy-api-proxy` on the Mac → ComfyUI on the GPU PC**. It does not use a hosted generation API.

1. Install the pinned ComfyUI/LTX node sources and the four required model files using [GPU setup and model paths](docs/MODELS.md).
2. Start ComfyUI on the GPU PC at a LAN/VPN address reachable from the Mac, port 8188.
3. Install the optional client dependencies on the Mac:

```bash
bash scripts/setup.sh --comfy
```

The client uses the official Python `comfy-sdk==0.5.0` and `comfy-api-proxy==0.1.6`, with transitive versions recorded in `requirements-comfy-lock.txt`; Node.js is not required.

Set these values in `.env`. Replace the documentation address `192.0.2.10` with the GPU PC's actual address:

```dotenv
FACETRUE_MODE=comfy
COMFYUI_URL=http://192.0.2.10:8188
COMFY_PROXY_URL=http://127.0.0.1:8189
```

Start the proxy and app in two Mac terminals:

```bash
bash scripts/run_proxy.sh
```

```bash
bash scripts/run.sh
```

Then run `.venv/bin/python scripts/doctor.py --require-gpu`. This checks proxy health, ComfyUI discovery, required node classes and model filenames. A successful diagnostic is **not** a successful inference run.

On a two-machine setup, `COMFYUI_URL=http://127.0.0.1:8188` would address the Mac rather than the GPU PC. `COMFY_PROXY_URL` stays on the Mac's loopback interface. This MVP is intended for a trusted local setup and does not provide multi-user authentication.

### Model defaults

The real graph uses an INT8 ConvRot LTX-2.5 distilled transformer, an INT8 ConvRot Gemma 4 text encoder, a Conv video VAE and the Restore IC-LoRA. It uses 8 distilled steps, CFG 1, and 960×544 spatial tiles. The default app canvas is **1280×736**, padded to model-compatible dimensions; it is not an exact 1280×720 encode. On the tested RTX 5090 with ComfyUI `--lowvram` it ran at a sampled whole-device peak of about 31.9-32.1 GB. Other setups are not guaranteed to fit. [Upstream lower-VRAM guidance](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui#lower-vram-model-files).

Keep `FACETRUE_STEPS=8`. The current workflow rejects other step counts instead of inventing a distilled schedule. Photo-guide streaming is disabled. The app controls temporal chunking explicitly.

Period presets supply positive and negative text. **At the default CFG 1, negative conditioning is skipped.** These presets do not guarantee historical accuracy. See [the inspected graph and node contracts](workflows/PROVENANCE.md).

## Command-line comparison

`--bbox` uses `x,y,width,height` in **normalized output pixels**. `--photo-bbox`, when supplied, uses pixels in the EXIF-oriented reference photo. The sample coordinates below must be replaced with your selection.

```bash
.venv/bin/python scripts/restore.py data/source.mp4 \
  --photo data/separate-photo.jpg \
  --bbox 500,150,220,260 \
  --output data/runs/example-001 \
  --seed 42 --preset vhs_1980s --deinterlace
```

Add `--synthetic` when the source was deliberately degraded for testing. Outputs must go to a new empty directory. In mock mode the output filenames and video notices identify input copies.

## Evaluate the photo effect

Prepare a clean clip, a separately captured correct-person photo, and a different-person photo. Do not use a target frame as the reference. The [evaluation guide](docs/EVALUATION.md) defines the manifest and the limits of the metric.

```bash
.venv/bin/python scripts/download_eval_models.py
FACETRUE_MODE=comfy .venv/bin/python scripts/evaluate.py data/evaluation/pilot.json \
  --output data/evaluation/run-001
```

The optional model download is explicit and hash-checked. Evaluation refuses mock output. `summary.csv`, `frames.csv`, and `run.json` retain paired deltas, missing detections, source hashes, settings and output provenance. A high similarity score alone does not prove faithful reconstruction.

### Pilot results (small test)

- **Material:** three public-domain White House clips (Barack Obama, Joe Biden, Michelle Obama). Each has a separate official portrait as the correct photo and a different person's portrait as the control. Sources are listed in [docs/DEMO.md](docs/DEMO.md#sources-and-licenses).
- **Settings:** seed 42, 97 frames, 8 steps.
- **Score:** SFace cosine against the clean original, on 13 sampled frames per clip. A face was detected in every sampled frame of every condition.
- **Damage was synthetic and heavy:** downscale to 1/5, blur, faded color, chroma shift, grain, H.264 CRF 36. It was applied by a local wrapper around `scripts/evaluate.py`; the repository default is milder.

| Clip | Damaged vs. original | No photo | Correct photo | Other person's photo | Correct − no photo | Correct − other | Frames won (vs. no photo / vs. other) |
|---|---|---|---|---|---|---|---|
| Obama | 0.680 | 0.728 | 0.861 | 0.694 | +0.133 | +0.167 | 13/13, 13/13 |
| Biden | 0.692 | 0.652 | 0.762 | 0.654 | +0.111 | +0.108 | 13/13, 13/13 |
| Michelle Obama | 0.608 | 0.773 | 0.804 | 0.783 | +0.031 | +0.020 | 12/13, 12/13 |

**What this does and does not show:**

- **Heavy damage:** in this small test, adding the correct photo helped the restored face look more like the real person, clearly for two clips and slightly for the third.
- **Mild damage:** with the repository's default damage, the damaged input was already about 0.87-0.89 similar to the original. There the effect was small and mixed: at 240 frames, correct − no photo was +0.014, +0.005 and −0.003.
- **Limits:** this is three clips and one seed. The result does not establish a general improvement.
- **Side effects:** the photo can also change the background (in the Biden pair, a flag became a dark wall) and color or sharpness.
- **Not proof of recovery:** a higher similarity score can partly mean the result looks more like the reference photo itself.

## Models and licenses

| Component | Role | Published terms / status |
|---|---|---|
| LTX-2.5 22B distilled | Core video model | LTX-2.x Community License |
| LTX-2.5 Restore IC-LoRA | Restoration adapter | LTX-2.x Community License |
| LTX-2.5 Conv video VAE | Video encode/decode | LTX-2.x distribution terms |
| Gemma 4 12B text encoder with LTX projections, Comfy INT8 (`Lightricks/LTX-2.5`, `text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`) | Local text conditioning | Distributed by Lightricks under the [LTX-2.x Community License](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x) ([model card](https://huggingface.co/Lightricks/LTX-2.5)); the Google Gemma 4 12B base model is [Apache-2.0](https://ai.google.dev/gemma/docs/gemma_4_license) ([model card](https://huggingface.co/google/gemma-4-12B-it)) |
| OpenCV Haar cascade | UI face proposals | Intel Open Source Computer Vision Library license in the classifier file |
| YuNet + SFace, optional | Evaluation detection and embeddings | YuNet MIT; SFace officially distributed Apache-2.0, exact training-data provenance **unverified** |

The INT8 Gemma 4 text encoder used here is Lightricks' customized package with LTX projections, so we treat it as governed by the LTX-2.x Community License rather than relabeling it Apache-2.0; Google's original Gemma 4 weights are Apache-2.0. Weights are downloaded locally from Hugging Face after a click-through access form; no hosted API is used.

Exact filenames, destinations and inspected license sources are in [docs/MODELS.md](docs/MODELS.md). Model access terms may require the user's own acceptance on Hugging Face. This app does not accept those terms automatically or include model weights.

App-owned code is [MIT](LICENSE). The adapted Lightricks workflow retains [its upstream license and notices](workflows/LICENSE.upstream.txt); MIT does not relicense upstream material or weights.

## Development and limitations

```bash
.venv/bin/python -m pytest -q
```

Tests cover configuration, workflow construction, crop geometry, chunk accounting, real FFmpeg media processing and comparison exports, mock job behavior, and evaluation safeguards. They do not establish LTX quality or GPU compatibility.

For an optional browser smoke, install `playwright==1.55.0` in a development environment and run `scripts/smoke_ui.py --browser-executable /path/to/chrome`. It starts its own loopback mock server with synthetic color-pattern inputs, checks the desktop/mobile UI, same-time seeking, downloads and reload recovery, and stops the server. It never opens your normal browser profile. The Mac run used `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.

Media, outputs, model weights, `.env`, caches and local evaluation records are gitignored. The app keeps uploaded media and job files in `FACETRUE_DATA_DIR` (default `data/`); remove local job data when no longer needed. No private family media is included in the repository.

Generative output may change identity, expression, age, color or objects. Fixed reference placement can become wrong as a person moves. Chunk boundaries can flicker. The app checks frame accounting, but visual seam quality still needs inspection on your own footage. The photo's effect has only been measured in the small pilot above.

[Technical report](docs/TECHNICAL_REPORT.md) · [Research notes](docs/RESEARCH_NOTES.md) · [Improvement plan](docs/IMPROVEMENT_PLAN.md) · [Development plan](docs/PLAN.md) · [GPU preflight](docs/GPU_PREFLIGHT.md) · [Evaluation](docs/EVALUATION.md) · [Demo plan](docs/DEMO.md) · [Sample provenance](samples/README.md)

## Challenge submission

The [official page](https://comfy.org/open-source-higgsfield/) lists October 30, 2026 at 09:00 PT as the deadline, which is **October 31 at 01:00 KST**. The project target is **October 30 at 22:00 KST**. The owner will handle repository visibility and the actual submission. The prepared materials are the app/source license and installation guide, a demo under two minutes, a model list, and a `#OpenSourceHiggsfield` post.
