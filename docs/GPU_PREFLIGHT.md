# RTX 5090 preflight and evidence record

**Status: real GPU inference has not been recorded.** Passing CPU tests or the mock UI flow does not establish that LTX fits in 32GB, finishes a clip, or benefits from the photograph. This procedure records those separate checks without filling in invented results.

The planned gate is defined in [PLAN.md](PLAN.md): complete 49 frames, 97 frames and a ten-second clip, then evaluate three controlled clips. The target configuration is one RTX 5090 32GB, the official INT8 transformer + INT8 Gemma + Conv VAE path, and offload if needed. Peak system RAM and render speed remain unmeasured.

## 1. Confirm the environment

Install [the pinned source versions and four model files](MODELS.md), configure the GPU PC's real address in the Mac's `.env`, and start the local proxy. Model access conditions must already have been reviewed and accepted by the account holder; a missing gated download is not bypassed by this app.

On the Mac:

```bash
.venv/bin/python scripts/doctor.py --require-gpu
```

The diagnostic is read-only. It checks FFmpeg, the client packages, proxy HTTP health, ComfyUI `/system_stats`, node classes and model filenames. It does not queue a workflow, check weight-file integrity through a full load, measure memory, or verify restoration quality. A proxy can be healthy while the GPU server is unavailable.

Record these facts with the run, under a gitignored `_support/` or `data/` directory:

| Field | Record from the actual GPU PC |
|---|---|
| GPU / VRAM | Exact device name and total memory from `nvidia-smi` |
| Driver / OS | Actual driver version and operating system |
| Python / PyTorch / CUDA | Versions from the ComfyUI Python environment |
| Source revisions | `git rev-parse HEAD` for ComfyUI and ComfyUI-LTXVideo |
| Package environment | `python -m pip freeze` from the ComfyUI environment |
| Weight provenance | HF revision and SHA256 of all four downloaded files |
| Startup flags | Include `--lowvram` and any offload/cache options actually used |
| Input / photo | File hashes and independent-photo provenance |
| Generation settings | Canvas, fps, frame count, seed, 8 steps, CFG 1, tile settings |

The app's render JSON records chunk wall time and marks unmeasured memory as unmeasured. It does not currently instrument the GPU allocator's peak or reliably split loading, sampling and decode time.

## 2. Run small inputs before a ten-second job

Use material that you are allowed to process. Keep the same output dimensions, seed and reference location while increasing frame count. Short hardware preflights may be shorter than the normal 4-10 second demo clips.

Make a 49-frame source at 24 fps:

```bash
ffmpeg -i data/source.mp4 -vf fps=24 -frames:v 49 -an \
  -c:v libx264 -pix_fmt yuv420p data/preflight-49.mp4
```

Then run both photo conditions through the app. Replace the example bbox with your selection on the normalized 1280×736 frame:

```bash
FACETRUE_MODE=comfy .venv/bin/python scripts/restore.py data/preflight-49.mp4 \
  --photo data/separate-photo.jpg --bbox 500,150,220,260 \
  --output data/preflight/run-49 --seed 42
```

Use a new output directory for each run. Repeat with `-frames:v 97` and `run-97`, then `-frames:v 240` and `run-240`. At 24 fps, 240 frames is ten seconds. The ten-second job exercises the 97/17 chain and final-window trimming. Leave photo-guide streaming disabled; this app supplies the windows and each arm's separate 17-frame history.

Check the actual output frame counts rather than assuming that a rendered MP4 contains all requested frames. Playback must include the first frame, every join, and the last frame. Both arms must retain matching timing, and the paired run must not reuse the photo arm's prefix in the no-photo arm.

If a 49-frame job fails, retain the ComfyUI error and reduce only one variable, such as output resolution, before retrying. Record the reduced configuration as a separate preflight. Do not describe a lower-resolution success as proof that the default HD-sized configuration fits.

## 3. Measure time and memory honestly

On the GPU PC, a sampled device-memory log can be recorded with:

```bash
nvidia-smi --query-gpu=timestamp,name,memory.used,memory.total,utilization.gpu \
  --format=csv -lms 200 > gpu-memory.csv
```

Run this in a separate terminal while the actual job runs; stop it after the job. Store the log outside tracked source. The maximum of this series is a **sampled whole-device VRAM maximum**, not necessarily the model's exact peak allocation. Record other GPU workloads and the polling interval.

Record the ComfyUI Python process's peak resident/working-set memory, plus peak system RAM usage, using an OS monitor or a process sampler. State the tool and sampling interval. Mac application RAM is a different quantity and must not be reported as GPU-PC RAM.

Measure complete request wall time from submission until the final video is available. Separate cold-model loading from a warm run. Cached ComfyUI nodes can skip work: record cache state, restart conditions and seed. If loading, sampling or VAE decode times are unavailable from instrumentation/logs, leave those fields **not measured** instead of deriving them from the total.

Use a table like this after running the jobs:

| Trial | Frames / size | No-photo completed | With-photo completed | Total time | Load / sample / decode | Sampled VRAM max | GPU-PC RAM max | Visual join check |
|---|---|---|---|---|---|---|---|---|
| Small preflight | 49 / 1280×736 | Yes | Yes | 110.4 s | Not measured | Not sampled | Not measured | One window, no joins |
| Window preflight | 97 / 1280×736 | Yes | Yes | 177.9 s | Not measured | Not sampled | Not measured | One window, no joins |
| Full short clip | 240 / 1280×736 | Yes (3 windows) | Yes (3 windows) | 482.4 s | Not measured | Not sampled | Not measured | Not recorded |

Results recorded on 10/29 (02:34-02:50 KST) on one RTX 5090 (32,607 MiB), ComfyUI started with `--lowvram`, 8 steps, CFG 1, seed 42. "Total time" is the `time` wall time of `scripts/restore.py`. It covers both arms plus comparison export, from a Mac through the proxy, so it is not a per-window rendering speed. Cache state between trials was not recorded. One earlier 49-frame attempt failed after 4.6 s with `ComfyJobFailed` (ComfyUI job status failed). The runs above came after it.

The identity-pilot runs (section 4) were sampled with `nvidia-smi` every 200 ms for the whole device:

| Pilot run | Renders | Wall time | Sampled VRAM max |
|---|---|---|---|
| 97 frames, repo-default damage | 9 × 97 frames | 661.5 s | 32,087 MiB |
| 240 frames, repo-default damage | 9 × 240 frames (3 windows each) | 2,086.6 s | 31,927 MiB |
| 97 frames, strong damage | 9 × 97 frames | 662.2 s | 31,927 MiB |

The strong-damage pilot averages about 74 s per 97-frame render, including evaluation overhead. GPU-PC system RAM was not measured.

Replace a cell only with a result from retained logs. Preserve failures, including out-of-memory errors. Do not use mock wall times as rendering speeds.

## 4. Run the three-arm identity pilot

Follow [EVALUATION.md](EVALUATION.md) to prepare three clean clips with independent correct-person and wrong-person photos, model hashes, source rights and bboxes. The script makes the controlled degradation and renders all three conditions with matching settings. The evaluation models are downloaded only when you explicitly run `scripts/download_eval_models.py`.

For a 49- or 97-frame manifest, `--direct` bypasses chaining to isolate the single-window path:

```bash
FACETRUE_MODE=comfy .venv/bin/python scripts/evaluate.py data/evaluation/pilot-97.json \
  --output data/evaluation/preflight-97 --direct
```

For a ten-second `frame_count: 240` manifest, use the normal chunked adapter:

```bash
FACETRUE_MODE=comfy .venv/bin/python scripts/evaluate.py data/evaluation/pilot-240.json \
  --output data/evaluation/preflight-240
```

Inspect `summary.csv`, `frames.csv` and `run.json`. Primary similarity compares each result to its clean HQ frame. Report the correct-minus-no-photo and correct-minus-wrong-photo differences for every clip, with common detection coverage. A completed job with insufficient coverage is inconclusive. A positive three-clip pilot is still not a general guarantee.

For a published demo of the deliberately degraded input, use `scripts/restore.py --synthetic` or the UI's synthetic-test checkbox to create visibly labeled comparison exports. Evaluation artifacts are private working files until deliberately selected for publication.

## 5. Decide what the evidence supports

- A successful health check supports connectivity and model discovery.
- A completed 49/97-frame job supports that specific single-window configuration.
- A completed 240-frame job with correct counts supports the implemented short-clip chain on that input.
- Paired score differences and visual inspection describe the tested clips; they do not prove historical truth or unrestricted reliability.

The project's continuation decision remains the explicit gate in [PLAN.md](PLAN.md). If the correct photo does not consistently help, record that result and reduce the product claim. Do not fill a comparison slot with an unrelated result or remove failed clips from the pilot without disclosure.
