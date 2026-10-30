# FaceTrue Restore Plan

## Implementation status

The app, CLI, comparison export, evaluation tools, and install and demo docs are implemented. The MVP checks below mean code plus CPU/mock verification. Real LTX restoration, RTX 5090 memory and speed, and the likeness gain from a photo were not yet verified at that point. Follow the [validation log](VALIDATION.md) and the [GPU preflight steps](GPU_PREFLIGHT.md).

## One-line idea
Give it an old family video (VHS or 8mm, black-and-white is fine) plus a separate photo of the person, and compare open-weights restoration with and without the photo on your own setup. The reference may influence the face; it does not guarantee a faithful likeness.

## Challenge info
- Deadline: 2026-10-31 01:00 KST. Target submission: 10/30 22:00 KST.
- Prizes targeted: Open Weights Only (RTX 5090), LTX VFX bonus ($2,000; LTX must be the core model)
- Submission form: https://form.typeform.com/to/V1dSQrkS
- The repo is private for now. Switch to public right before submission.

## Features
### MVP
- [x] Three-way comparison (the core differentiator): original / restored without photo / restored with photo, on the same frames
- [x] Click a face + drop a photo → reference canvas built automatically (gray canvas at output size, face pasted at the face position, frame_idx -1)
- [x] Automatic split and stitch (97-frame windows, 17-frame overlap)
- [x] Deinterlacing
- [x] Era-specific positive/negative prompt presets (negative conditioning is not applied at the default CFG 1)
- [x] Wipe-comparison MP4 export
- MVP limits: one person, 4-10 s clips, fixed framing first

### Later
- [ ] Re-place the reference per window when the face moves (face tracking)
- [ ] Multiple people, longer clips
- [ ] Seam review screen

## Architecture
- 5090 PC (32 GB): ComfyUI (8188) ← comfy-api-proxy (127.0.0.1:8189) ← comfy-sdk
- App: FastAPI + thin web UI, FFmpeg/OpenCV (deinterlace, split, stitch, comparison video)
- Model: LTX-2.5 22B + Restore IC-LoRA. Card settings: 8 steps, CFG 1, 960x544 tiles, 97-frame windows / 17-frame overlap
- Low VRAM: INT8 transformer + INT8 Gemma + offload, 64 GB+ RAM recommended
- The reference path requires use_streaming off

## 10/28 morning kill gate (if it fails, drop this and move to OIBC)
- [x] Finish 49 frames with the official low-VRAM settings (10/29, RTX 5090, `--lowvram`, both conditions 110.4 s)
- [x] Finish 97 frames (10/29, both conditions 177.9 s)
- [x] Finish a 10 s clip (240 frames, 3 windows × both conditions, 482.4 s). This preflight did not sample VRAM; the separate 240-frame pilot sampled a whole-device peak of 31,927 MiB. Per-stage time for loading, sampling and decoding, and GPU-PC RAM, were not measured.
- [x] Compare no reference / correct reference / wrong-person reference with the same seed on 3 artificially degraded clips (public-domain Obama, Biden, Michelle; seed 42; 97 and 240 frames)
- [x] The correct reference is consistently more similar than no reference: under strong degradation (1/5 downscale, CRF 36), correct − none is +0.133 / +0.111 / +0.031 across the three clips, and also higher than the wrong-person reference. Under the default degradation the difference is within ±0.02, so it is not evidence either way
- Continue condition: the correct reference must be consistently more similar, and at least one file must finish end to end. Otherwise stop.
- Verdict (10/29): pass. Continuing based on visual review of the outputs and the strong-degradation numbers. This is a 3-clip pilot, not a general guarantee.

## Schedule (KST)
- 10/28 morning: kill-gate tests
- 10/28 afternoon: reference canvas generation, split/stitch pipeline
- 10/29: three-way comparison UI, deinterlacing, presets, wipe MP4 export
- 10/30 daytime: demo video (2 min or less), README install guide, social post
- 10/30 22:00: submit

## Demo
- First 10 s: the real photo next to the restoration without photo and the restoration with photo, side by side
- Sources: public-domain Prelinger home movies, etc.
  (e.g. https://commons.wikimedia.org/wiki/File:Home_Movies_-_Western_U.S.,_New_Mexico,_Mexico,_California,_Colorado,_Utah.webm)
- The reference must be a separate photo. Never use a frame from the clip being restored as the reference.
- Label artificially degraded test clips on screen

## Submission checklist
- [x] README install guide, licenses and model list complete
- [ ] Switch repo to public
- [x] 2-minute demo script and source-check document ([DEMO.md](DEMO.md))
- [ ] URL of the actual demo video (2 min or less)
- [ ] URL of the #OpenSourceHiggsfield social post
- [ ] Fill in the model list (LTX-2.5 22B, Restore IC-LoRA, Gemma encoder)
- [ ] Typeform submission

## Risks and honest positioning
- Similar research already exists: IP-FVR, RG-FVR (reference-photo-based face video restoration)
- Topaz Image already has reference-photo face restoration (Topaz Video not checked)
- LTX Restore HF Spaces already exist: winterwarrior/ltx-restore-demo, breslavsky/ltx-restore-studio
- The photo may not actually improve likeness → checked by the 10/28 gate
- The recorded render time and sampled VRAM apply to one RTX 5090 setup; GPU-PC RAM and per-stage times were not measured
- Reference + long-clip stitching may conflict
- Restoration is generative, so color and detail are reconstructed, not recovered
- Do not claim: "no length limit", "Veo/Sora refuse videos of children" (the Sora product shut down on 2026-04-26)
- What to highlight: a local open-weights app that shows the effect of the photo by directly comparing original / no-reference / reference restoration
