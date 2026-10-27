# Restore workflow provenance

`restore.api.json` is an **adapted API-format graph**, based on the official
Lightricks tiled upscale workflow. It is not an unmodified official API export.
The graph and node input contracts were checked against the sources below on
2026-10-27. A successful GPU run has not yet been recorded.

## Sources and pins

- Official Restore model card:
  <https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore>
- Official UI workflow:
  <https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/example_workflows/2.5/LTX-2.5_V2V_TiledFusion_Upscale.json>
- LTX node source pin: `220e1d45aa0469f518e982102fca4dca92a61862`.
  `iclora.py` defines the guide and LoRA loader. `tiled_fusion_sampler.py`
  defines the sampler and its guide cropping.
- Tiled sampling guide:
  <https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/tiled_fusion_sampler.md>
- ComfyUI core node contract pin: `426f5eea52a7ece1dd599fff4cb6cd1f352ddd24`.
  `nodes.py`, `comfy_extras/nodes_lt.py`, and `comfy_extras/nodes_video.py`
  supply the loaders, prefix guide, and video nodes.
- Official lower-VRAM file list:
  <https://docs.ltx.io/open-source-model/integration-tools/comfy-ui#lower-vram-model-files>
  and <https://huggingface.co/Lightricks/LTX-2.5>.

## Changes from the official UI graph

1. Flatten the functional video path into API nodes. Remove UI notes, previews,
   subgraph wrappers, all `GemmaAPITextEncode` nodes, prompt-enhancement branches,
   and optional audio-generation components. Prompts use local `CLIPTextEncode`.
2. Replace Refine Details with
   `ltx-2.5-22b-ic-lora-restore-1.0.safetensors` at strength 1.0.
3. Use the official lower-VRAM stack: INT8 ConvRot distilled transformer,
   INT8 ConvRot Gemma 4 encoder, and BF16 Conv video VAE. `UNETLoader` uses
   `weight_dtype=default`; quantization is encoded in the checkpoint file.
4. Use 960x544 spatial tiles, 0.5 overlap, 0.05 blending variance, Euler, CFG 1,
   and the fixed eight-step distilled sigma sequence. The Python builder rejects
   any `steps` value other than 8 rather than inventing an untested schedule.
5. Add a second `LTXAddVideoICLoRAGuide` for the photo canvas at `frame_idx=-1`.
   The no-photo variant removes this guide and its `LoadImage` node completely.
6. Keep `use_streaming=false` and `use_tiled_encode=false` on IC-LoRA guides.
   The app handles each 97-frame window. The sampler uses `tile_frames=0`, so
   it processes that single window with spatial tiling. Tiled VAE *decode* is
   enabled; spatially tiled guide *encoding* is disabled, as upstream recommends.
7. For a subsequent window, attach its own comparison arm's last 17 restored
   frames with core `LTXVAddGuide` at frame 0 before the optional photo guide.
   The caller uploads precisely those 17 frames. App-level stitching removes or
   blends the overlap. The model must not receive the whole clip as one window.
8. Render silent video. Source audio can be preserved separately by FFmpeg.
   The Restore LoRA is not trained for audio generation.

The API graph uses current ComfyUI `SaveVideo` DynamicCombo keys:
`format`, `format.codec`, and `format.codec.encoding`. Install compatible current
ComfyUI and the pinned LTX nodes; old releases may not expose these inputs.

## Runtime contract

- Upload input clips and canvases to ComfyUI before calling `build_workflow`.
  Pass the returned relative input names, never the client's absolute paths.
- Each window has `8*n+1` frames and at most 97 frames. Pad only the last window,
  and trim generated padding when stitching. Both dimensions are multiples of 32.
- The canvas matches the output dimensions. Place a separate photo's face crop
  over the selected person's position. A face elsewhere on the canvas reaches
  different spatial tiles. No tracking or per-window repositioning is implemented.
- The app must preserve framing and aspect ratio during preprocessing. The
  graph's resize assumes the uploaded window is already normalized to the canvas.
- No-photo and photo arms use the same per-window seed and generation settings.
  Each arm keeps its own prefix history. Never feed photo-arm results into the
  no-photo arm.
- At CFG 1, ComfyUI's standard sampler skips negative conditioning. Negative
  presets are retained in the graph for transparency, but are **not an effective
  safeguard against anachronisms at this default**. Do not claim that they prevent
  inventions. Changing CFG requires a separately validated experiment.
- Quantized filenames are an official lower-VRAM recommendation, not a measured
  guarantee that this graph fits an RTX 5090 for every input. The 49/97-frame GPU
  smoke runs and memory measurements are still required.

## Licenses

The original ComfyUI-LTXVideo repository contains the **LTX-2 Community License
Agreement**, dated January 5, 2026. Its unchanged license is included as
`LICENSE.upstream.txt` for the derived workflow. The adaptation notices above
describe the changes. Original attribution belongs to Lightricks.

App-owned Python code is covered by the repository's MIT license. That does not
relicense upstream assets or model weights. LTX-2.5 and Restore weights link to
the **LTX-2.x Community License**:
<https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x>.
Check the applicable Gemma terms for the exact encoder distribution as well.
No weights are distributed here. Hugging Face may require the user to accept
the model's access conditions before downloading.
