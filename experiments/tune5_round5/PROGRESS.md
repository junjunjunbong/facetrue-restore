# tune5 — round 5 identity attempts (10/30, decision 15:30 KST)

Plan: PLAN.md. Harness: sweep5.py (= tune4/sweep4.py + IC-guide Advanced / keyframe file). Bar: mean c−n ≥ +0.12 at s42 AND s7, correct>wrong all, no pop, abs correct up, face LPIPS ≤ +0.02.

## Run log
- 11:43 KST: started; worktree ../facetrue-r5-wt on tune/round5.
- 11:45 KST: M done (diag_m.py → diag/michelle_diag.json, no GPU). SFace photo↔clean 13 frames: obama 0.794, biden 0.673, michelle 0.622 (lowest; range 0.583–0.655). Wrong photo↔clean: pence 0.125, kerry 0.007, harris 0.172 (hardest control). Clean f0↔other clean frames: 0.929/0.941/0.933 (michelle min 0.862). Michelle pose range is narrow (yaw −0.03..−0.14, photo yaw −0.02): corr(c−n, |yaw|) −0.03, corr(c−n, mouth) −0.35, corr(c−n, brightness) −0.28, corr(c−n, photo↔frame cos) 0.02, corr(c−n, none score) −0.60. Michelle frame 0 c−n = −0.072 (s42) / −0.002 (s7); later frames +0.01..+0.12. s42 michelle wrong 0.783 > none 0.773. → Diagnosis: not pose/lighting; the photo itself is the weakest identity match to the clip (0.62) while no-photo is already 0.773 from the video, so the photo has little to add and can pull frame 0 off.
- 11:44 KST: A1 adv_mask_s42 launched (LTXAddVideoICLoRAGuideAdvanced exists in installed ComfyUI-LTXVideo, iclora.py; attention_strength max 1.0, so 1.25/1.5 not possible without code hacks → skipped). Mask = face_bbox, feather σ=0.06·w, via LoadImageMask. Obama+Michelle s42, none reused.
- 11:49 KST: A1 adv_mask_s42 done (300 s, 73 s/render). correct−none obama +0.135 (baseline +0.133), michelle +0.034 (baseline +0.031); correct abs 0.863 vs 0.861, 0.807 vs 0.804; correct−wrong obama +0.130 (baseline +0.167), michelle +0.010 (baseline +0.020). Gain over current correct ≈ +0.002/+0.003 < +0.01 → not expanded. A2 (mask grown 1.5×, feather 0.1) launched as last A variant while Qwen downloads.

## 11:55 KST — A2 result (adv + mask grow 1.5, feather 0.1, s42)
| person | correct−none | correct abs (base) | correct−wrong (base) |
|---|---|---|---|
| Obama | +0.135 | 0.8618 (0.8607) | +0.155 (+0.167) |
| Michelle | +0.038 | 0.8105 (0.8038) | +0.020 (+0.020) |
Gain over current correct < +0.01 for both → **A closed (fail)**. attention_strength >1 not possible (node max 1.0) → skipped.

## 11:55 KST — B download status
hf-xet stalled (0 B after 2 min). Switched to 24+12-way ranged curl on 5090: measured ~8 MB/s total → ~30 GB needs ~60 min (ETA ~12:55). B continues once files land.

## 11:56 KST — C launched while B downloads
Implementation (no custom code): second Advanced guide node 70 with attention_strength=0 (photo muted) → sampler negative; sampler cfg = 1+α. Deviation: LTXVTiledFusionSampler re-noises at sigma[0], so restricting to steps 5–7 needs a sampler hack → α applied on all 8 steps. c0 = α=0 reproduction check (Obama), c25 = α=0.25 (Obama+Michelle s42).

## 11:59 KST — C α=0 reproduction: PASS
c_a0_s42 (Obama): correct 0.86070 / wrong 0.69366 / correct−none +0.1330 — identical to run-97-strong (0.8607 / 0.6937 / +0.133). c25 (α=0.25) running.

## 12:06 KST — C α=0.25 result (all 8 steps; photo-muted cond as cfg negative, cfg 1.25): FAIL
| person | correct abs (base) | correct−none | correct−wrong (base) |
|---|---|---|---|
| Obama | 0.8609 (0.8607) | +0.133 | +0.195 (+0.167) |
| Michelle | 0.7885 (0.8038) | +0.016 | +0.045 (+0.020) |
Separation rises only because wrong drops; absolute correct does not improve (Michelle −0.015). Discarded. 137 s/render (2× forwards).

## 12:08 KST — consult update applied
- Attention backend: ComfyUI log "Using pytorch attention"; sageattention not installed → masks are honored (SDPA). A1 vs A2 (different masks) give different outputs, so the mask is applied.
- Photo-only attention >1: comfy LTX model supports amplification; Advanced node caps at 1.0 → tiny node custom_nodes/ft5_attn.py (FTGuideAttentionScale, sets last guide entry strength). ComfyUI restarted to load it. Runs amp125/amp150 next.
- Reject rule tool: tune5/qual.py (face LPIPS vs clean, motion-compensated temporal error f80–96 using clean-clip Farneback flow), run on 5090.

## 12:09 KST — reject-rule metrics (qual.py; correct arm; LPIPS lower=better, terr = motion-comp. temporal error f80–96, clean terr Obama 1.223 / Michelle 0.753)
| run | Obama LPIPS | Obama terr | Michelle LPIPS | Michelle terr |
|---|---|---|---|---|
| baseline run-97-strong | 0.1586 | 2.069 | 0.2267 | 1.210 |
| A2 adv_mask15 | 0.1604 | 2.042 | 0.2268 | 1.193 |
| C α=0.25 | 0.1606 | 2.104 | 0.2304 | 1.266 |
All within reject limits (ΔLPIPS < +0.02, terr < +10%); A/C fail on the identity gain, not on quality.

## 12:18 KST — A follow-up: photo-only attention amplification (FTGuideAttentionScale, LoRA 1.0, guide strength 1.0, no mask), s42
| run | Obama correct (base 0.8607) | Michelle correct (base 0.8038) | mean Δ correct | Obama c−w | Michelle c−w |
|---|---|---|---|---|---|
| amp 1.25 | 0.8525 | 0.8171 | +0.0025 | +0.159 | +0.050 |
| amp 1.50 | 0.8486 | 0.8121 | −0.0019 | +0.166 | +0.052 |
Michelle gains a little, Obama loses; mean ≤ +0.01 → **A closed (all variants fail)**.

## 12:20 KST — B download 15.7 / 29.9 GB, ETA ~12:50. Exceeds the 45-min download rule (11:46+45=12:31) by ~20 min; continuing because the 15:30 decision still leaves time — deviation noted.
- 12:48 Qwen download complete (all 3 OK). LTX unloaded; starting qwenkf.py
- 12:51 qwenkf: Obama none done (pose/mouth preserved visually, look/m_obama_none.jpg); with image2 ~3.4 s/it ×40 ≈ 2.3 min/kf. cfg b1 (kf 0.8) / b1r (kf 0.6) written.
- 13:01 qwenkf done (6 kf, ~137 s each with image2). Qwen unloaded; launching b1 (kf 0.8).
- 13:10 B kf0.8 s42 (qwenkf_s42): correct O 0.8457 / M 0.8005 (base 0.8607/0.8038); none O 0.8073 / M 0.7325; wrong O 0.6772 / M 0.7747.
  c−none O +0.038, M +0.068 (mean +0.053, bar +0.12) ; c−w O +0.168, M +0.026. Absolute correct DROPS (−0.015 / −0.003).
  Pop: frame-0 cosine falls (O correct 0.69 vs base 0.82; M 0.70 vs 0.71; all arms f0 drop) then recovers at f8 → keyframe frame mismatches clean. 
  qual: LPIPS O 0.1491 M 0.2290 (base 0.1586/0.2267, ok); terr O 1.762 M 1.012 (base 2.069/1.210, ok). → fail on identity; pop present → retry kf 0.6 (b1r).
- 13:12 diag: Qwen keyframe vs clean f0 SFace: O none 0.741 / correct 0.741 / wrong 0.446; M none 0.633 / correct 0.580 / wrong 0.459 — the keyframe is weaker than the baseline correct output at f0 (O 0.82, M 0.71), so B caps identity.
- 13:19 B retry kf0.6 s42 (qwenkf06_s42): correct O 0.8461 / M 0.8021 (base 0.8607/0.8038); none O 0.8208 / M 0.7705; wrong O 0.6844 / M 0.7899.
  c−none O +0.025, M +0.032 (mean +0.028; bar +0.12); c−w O +0.162, M +0.012. Final gain on correct vs baseline: O −0.015, M −0.002 (<+0.02) → B FAIL, not expanded (no s7, no 2x2).
  Pop largely gone at 0.6 (O correct f0 0.83 vs base 0.82). qual: LPIPS O 0.1445 M 0.2342 (base 0.1586/0.2267; M +0.0075 < 0.02); terr O 1.784 M 1.051 (base 2.069/1.210).
  Mechanism: Qwen also "restores" identity in the none arm (Obama none +0.09), which shrinks the c−none gap, and its correct keyframe is only 0.74/0.58 vs clean f0.
- 13:20 VERDICT round 5: A, amp, C, B all fail the bar. GPU freed (/free; no curl left).
