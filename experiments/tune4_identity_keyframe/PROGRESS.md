# tune4 — round 4 identity attempts (10/30, hard stop 15:00 KST)

Harness: sweep4.py = tune3/sweep3.py + `ref_extra_strength`. Strong damage, 97 frames, 3 clips, none arm reused from baseline of same seed.
Bar: mean c−n ≥ +0.12 at seeds 42 AND 7, correct>wrong for all 3 people at both seeds, no visible pop.
Note: the reference guide (node 14) uses frame_idx −1, which LTXVAddGuide resolves to the LAST frame (96). Guides are appended tokens (cropped by LTXVCropGuides), not overwritten frames.

## Run log
- 09:05 KST: A queue started (nohup, runq.log): mp_0_48_s42 (extra ref guides at 0,48), mp_48_s42, mp_24_48_72_s42, mp_0_48_lo_s42 (extras at 0.6).
- 09:13 KST: a1 mp_0_48_s42 (extra ref guides at frames 0,48, strength 1.0) done, 449 s. correct−none: obama +0.143, biden +0.079, michelle −0.020 → mean +0.067 (baseline s42 +0.092). Worse; michelle hurt again. correct−wrong +0.234/+0.167/+0.102.
- 09:14 KST: a2 mp_48_s42 started. 5090 downloads restarted (IP-Adapter plus-face, RealVisXL vae/te done; te2+unet pending). RealVisXL V4.0 license verified = openrail++ (HF API), h94/IP-Adapter = apache-2.0.
- 09:21 KST: a2 mp_48_s42 done, 454 s. correct−none: obama +0.150, biden +0.090, michelle +0.013 → mean +0.084 (< baseline +0.092). correct−wrong +0.231/+0.094/+0.053 (separation worse than baseline on biden/michelle).
- 09:25–09:37 KST: B1 = SDXL img2img (RealVisXL V4.0, openrail++) + IP-Adapter plus-face SDXL ViT-H (Apache-2.0; CLIP ViT-H laion encoder, no insightface) on the FFHQ-aligned frame-0 face, IP image = the arm's reference photo. Grid: ip scale {0.5,0.7,1.0} × denoise {0.15,0.25,0.35,0.5,0.65,0.8} × init {no-photo LTX f0, arm's own LTX f0}; 1.75 s/img, peak 13.4 GB (needed ComfyUI /free first). Scores in kfscores4.json, table via paste4.py.
  - Keyframe-alone frame-0 SFace vs GT (mean over 6 seed×clip, correct arm): every denoise ≥0.35 is BELOW the no-photo frame 0 (0.726): best 0.666 (ipa0.5, 0.35, arm init); 0.5 → ~0.49; 0.8 → ~0.38–0.45. IP-Adapter plus-face does not carry the identity; it erodes it.
  - Denoise 0.15/0.25 with arm init "pass" the gate (0.760/0.740) but control raw_ltxarm (arm's own frame 0 pasted, no SDXL) = 0.760 corr / 0.678 wrong → IP-Adapter adds +0.000. B1 = FAIL (no full eval: nothing it adds over the existing arm).
- 09:47 KST: a3 mp_24_48_72_s42 done, 479 s. correct−none: obama +0.149, biden +0.104, michelle +0.022 → mean +0.092 (= baseline +0.092). correct−wrong +0.199/+0.147/+0.095 (mean +0.147 vs baseline +0.098). No gain on the target metric.
- 09:48 KST: B2 (DIAGNOSTIC, LICENSE CONFLICT) = InstantID img2img (InstantX/InstantID Apache-2.0 + ControlNet kps) on RealVisXL, face embedding from insightface antelopev2 glintr100.onnx (official GitHub release v0.7; NON-COMMERCIAL research-only) via onnxruntime, no insightface package. Script r4/iid_kf.py. Smoke test ips0.8 cn0.8 denoise0.5 init=no-photo LTX: keyframe corr/wrong mean 0.701/0.202 (obama 0.855/0.863 corr; michelle 0.619/0.584) → fail gate, but identity transfer is strong (wrong drops to ~0.2).
- 09:54 KST: B2 grid running on 5090 (ips {0.8,1.0} × denoise {0.3,0.4,0.5,0.65} × init {ltx, ltxarm}), ~3 s/img, 192 imgs. Note: launched under `timeout 770` in an ssh session (not nohup) before the interruption; still alive, left to finish instead of restarting.
- 10:00 KST: B2 grid done (192 imgs). Keyframe-alone frame-0 SFace (mean of 6, corr/wrong): denoise 0.3 → 0.741–0.745 / 0.41–0.43 (PASS gate >0.726 and corr>wrong all 6); 0.4 → ~0.70–0.71 (fail); 0.5 → ~0.69–0.70; 0.65 → ~0.67. ips 0.8 vs 1.0 makes ~no difference. Per clip at 0.3/ltx: obama 0.877/0.868 (vs no-photo 0.720/0.771), biden 0.686/0.701 (vs 0.689/0.661), michelle 0.678/0.640 (vs 0.784/0.730) → michelle keyframe is WORSE than no photo.
- 10:01 KST: full eval b1 iid_kf_s42 (keyframe iid1.0c0.8_0.3_ltx, per-arm correct/wrong keyframes) launched with nohup on the Mac (log b1.log).
- 10:12 KST: b1 iid_kf_s42 done, 499 s. correct−none: obama +0.105, biden +0.042, michelle −0.015 → mean +0.044 (baseline +0.092). correct−wrong +0.269/+0.189/+0.069 (mean +0.176; the wrong-photo keyframe drags the wrong arm down, it doesn't lift the correct arm). Correct-arm video SFace fell even for obama (0.833 vs baseline 0.861) despite a 0.877 keyframe. B2 = FAIL at s42 → no s7 run. (Also license-conflicted, antelopev2.)
- 10:13 KST: a4 mp_0_48_lo_s42 (extras at 0,48, strength 0.6) launched (nohup, a4.log).
- (time note: earlier entries' clock was ~2 min ahead; from here times are the Mac's `date`.)
- 10:12 KST: C prep. Second PD photos (US federal government works, Wikimedia Commons) in data/eval-pd/src/*-photo2.jpg:
  obama ← https://upload.wikimedia.org/wikipedia/commons/9/9d/Barack_Obama.jpg ; pence ← "Mike Pence, official portrait, 112th Congress.jpg" ; biden ← "Joe Biden presidential portrait.jpg" ; kerry ← "John Kerry official portrait.jpg" ; michelle ← "Michelle Obama official portrait.jpg" ; harris ← "Senator Harris official senate portrait.jpg". (2009 Souza Obama portrait rejected: CC BY 3.0.)
  SFace photo↔photo2: obama 0.841, pence 0.773, biden 0.718, kerry 0.807, michelle 0.639, harris 0.761. Canvases checked visually (look/c2sheet.jpg).
- 10:12 KST: sweep4.py gained `ref2` (per clip/arm second photo → canvas via ev._canvas → scp to ComfyUI/input → LoadImage 51 + extra IC-LoRA guide 52.. at `ref2_idx`). Configs c1 ref2_end_s42 (idx −1), c2 ref2_48_s42 (idx 48). chainC.sh (nohup) runs c1 then c2 after a4 exits.
- 10:19 KST: a4 mp_0_48_lo_s42 done, 548 s. correct−none obama +0.128, biden +0.056, michelle −0.000 → mean +0.061 (baseline +0.092); correct−wrong +0.170. FAIL. Hypothesis A closed: best A = a3 +0.092 = baseline, no gain. c1 ref2_end_s42 started (obama correct 88 s, ref2 canvas upload worked).
- 10:32 KST: c1 ref2_end_s42 done, 812 s (two photo guides at −1 are ~1.6× slower). correct−none obama +0.131, biden +0.073, michelle +0.018 → mean +0.074; correct−wrong obama +0.173, biden −0.003, michelle −0.001 (wrong ≥ correct for 2 clips). FAIL. c2 ref2_48_s42 running.
- 10:44 KST: note: data/eval-pd/synth shares the same ComfyUI queue (queue: 1 running, 2 pending at 10:44), so c1/c2 wall times include queue wait; the "1.6× slower" remark above is not a clean measurement. Do not /free or kill while synth jobs are queued.

## VERDICT A — multi-position reference guide (s42, bar: mean correct−none ≥ +0.12 at s42 and s7, correct>wrong all clips)
| run | obama | biden | michelle | mean c−none | mean c−wrong |
|---|---|---|---|---|---|
| baseline run-97-strong | | | | +0.092 | |
| a1 mp_0_48 | +0.143 | +0.079 | −0.020 | +0.067 | +0.168 |
| a2 mp_48 | +0.150 | +0.090 | +0.013 | +0.084 | +0.126 |
| a3 mp_24_48_72 | +0.149 | +0.104 | +0.022 | +0.092 | +0.147 |
| a4 mp_0_48 @0.6 | +0.128 | +0.056 | −0.000 | +0.061 | +0.170 |
FAIL. No variant beats baseline at s42 (best a3 ties it), so no s7 runs. Extra copies of the same photo raise obama a bit and do nothing for michelle.

## VERDICT B — identity-conditioned frame-0 keyframe
- B1 IP-Adapter plus-face + RealVisXL img2img: FAIL at the keyframe gate (corr ≤ 0.666 at denoise ≥0.35; at 0.15, 0.760 = the raw no-photo control 0.760, so no identity gain).
- B2 InstantID (needs insightface antelopev2, NON-COMMERCIAL) passed the gate (0.742) but the full eval iid_kf_s42 got mean +0.044 (obama +0.105, biden +0.042, michelle −0.015). FAIL, plus a license conflict. No s7 run.
- 10:53 KST: c2 ref2_48_s42 done (1090 s wall incl. shared queue). correct−none obama +0.143, biden +0.092, michelle +0.035 → mean +0.090; correct−wrong +0.225/+0.072/+0.051 (correct>wrong all 3). Best michelle so far, but mean = baseline (+0.092) → FAIL. Launching c3 = photo2@48 + photo1 extras @24,72 (nohup, c3.log), last try.
- 11:10 KST: c3 ref2_48_x24_72_s42 done (857 s wall incl. shared queue). correct−none obama +0.151, biden +0.114, michelle +0.017 → mean +0.094; correct−wrong +0.245/+0.150/+0.095 (correct>wrong all 3). Highest mean of round 4, but +0.002 over baseline is within noise and far below the +0.12 bar → FAIL. No s7 run.

## VERDICT C — second PD photo as an extra guide (s42)
| run | obama | biden | michelle | mean c−none | mean c−wrong |
|---|---|---|---|---|---|
| baseline run-97-strong | | | | +0.092 | |
| c1 photo2 @−1 | +0.131 | +0.073 | +0.018 | +0.074 | +0.056 (biden, michelle wrong ≥ correct) |
| c2 photo2 @48 | +0.143 | +0.092 | +0.035 | +0.090 | +0.116 |
| c3 photo2 @48 + photo1 @24,72 | +0.151 | +0.114 | +0.017 | +0.094 | +0.163 |
FAIL. Michelle stays near +0.02–0.035 in every variant and caps the mean.

## ROUND 4 OVERALL: nothing reached the bar (≥ +0.12 at s42 and s7). The shipped baseline stays as is. No improve_v4 videos made. Experiments stopped at 11:10 KST.
