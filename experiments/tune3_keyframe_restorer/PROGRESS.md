# tune3 — keyframe generator swap (GFPGAN v1.4, CodeFormer) — started 10/29 23:55 KST

Same pipeline as tune2 kf_rid: restored face pasted on the seed's no-photo LTX frame 0, fed as the frame-0 keyframe
(LTXVAddGuide@0, strength 1.0) to the correct and wrong arms. none arm reused from the baseline run of the same seed.
GFPGAN/CodeFormer take no reference photo, so correct and wrong arms get the SAME keyframe.
Restorers run on the 5090 with ComfyUI's venv + spandrel 0.4.2 / spandrel_extra_arches 0.2.0 (pure PyTorch, no compile),
~/facetrue-extra/fr/fr_run.py, peak 1.1 GB VRAM, ~6 s total. Input = FFHQ-aligned 512 crop of degraded frame 0 (src deg)
or of the no-photo LTX frame 0 (src ltx). Pre-registered for full runs: gfpgan_deg and CodeFormer default w=0.5 (cf0.5_deg).

## Keyframe-vs-GT frame 0 (SFace), before any render
| keyframe | s42 obama | s42 biden | s42 michelle | s7 obama | s7 biden | s7 michelle | mean |
|---|---|---|---|---|---|---|---|
| ltx_frame0(no kf) | 0.72 | 0.689 | 0.784 | 0.771 | 0.661 | 0.73 | 0.726 |
| cf0.5_deg | 0.726 | 0.632 | 0.703 | 0.746 | 0.567 | 0.691 | 0.677 |
| cf0.7_deg | 0.73 | 0.675 | 0.708 | 0.723 | 0.635 | 0.715 | 0.698 |
| gfpgan_deg | 0.768 | 0.709 | 0.705 | 0.766 | 0.673 | 0.708 | 0.721 |
| cf0.5_ltx | 0.704 | 0.632 | 0.737 | 0.716 | 0.627 | 0.71 | 0.688 |
| cf0.7_ltx | 0.713 | 0.647 | 0.753 | 0.741 | 0.644 | 0.706 | 0.701 |
| gfpgan_ltx | 0.712 | 0.597 | 0.768 | 0.761 | 0.607 | 0.723 | 0.695 |
None of the restored keyframes is closer to GT than LTX's own no-photo frame 0 on average (oracle = 1.0).
Expectation: no big gain. Full renders run anyway to measure.

## Run log
- 23:58 KST: queue started (nohup, runq.log): kf_gfpgan_deg_s42, kf_gfpgan_deg_s7, kf_cf0.5_deg_s42, kf_cf0.5_deg_s7.
- 00:05 KST: restored faces keep the degraded clip's faded colors (sheet_kf.jpg). Added color-matched variants (degc, LAB transfer to the no-photo LTX face, as kf_rid's degbc). Queued kf_gfpgan_degc_s42/s7 after the first queue (runq2.log).
- 00:06 KST: **kf_gfpgan_deg_s42** done (476 s): c−n +0.002 (obama +0.025, biden +0.023, michelle −0.043), c−w +0.015. Worse than baseline +0.092 and kf_rid +0.031. The keyframe sets identity and the photo stops mattering (c−w ≈ 0). Remaining queue continues for completeness.
- 00:43 KST: done so far: kf_gfpgan_deg_s7 (00:13), kf_cf0.5_deg_s42 (00:21), kf_cf0.5_deg_s7 (00:29), kf_gfpgan_degc_s42 (00:37). kf_gfpgan_degc_s7 running (started 00:37). Agent was interrupted once; nohup queue unaffected.
- 00:45 KST: all 6 runs done. Full table in summary.md (summarize3.py).

## Result (mean over 3 people × 13 frames, SFace)
| run | c−n s42 | c−w s42 | c−n s7 | c−w s7 |
|---|---|---|---|---|
| baseline (no kf) | +0.092 | +0.098 | +0.064 | +0.086 |
| kf_rid (tune2) | +0.031 | +0.082 | – | – |
| GFPGAN v1.4 (deg) | +0.002 | +0.015 | −0.008 | +0.016 |
| GFPGAN v1.4 (deg, color-matched) | −0.008 | +0.008 | −0.025 | +0.005 |
| CodeFormer w=0.5 (deg) | −0.033 | −0.000 | −0.031 | +0.006 |

## Verdict: do not use
No generator meets the bar (≥ +0.13 on both seeds, c>w for all 3). All are below baseline and below kf_rid. A photo-free restored keyframe fixes identity for the whole clip and drowns out the reference (c−w ≈ 0). No restored keyframe is closer to GT than LTX's own frame 0 (0.726). No improve_v3 videos/still made.
