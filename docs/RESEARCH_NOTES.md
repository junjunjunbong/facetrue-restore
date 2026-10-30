# Research notes: external literature review (2026-10-30)

> **What this is.** An English summary of an external research consult on improving identity fidelity in FaceTrue Restore (8-hour budget, one RTX 5090 32 GB, LTX-2.5 Restore in ComfyUI, open weights only). It is **not** a set of results we ran. The consult checked papers, official repositories, model cards and node source code as of 2026-10-30; it did not install or run anything on our GPU.
>
> **Caveats from the consult.** Reaching the acceptance bar is not guaranteed. ArcFace scores in papers cannot be converted into SFace gains on our three clips. All "expected gain" statements are prioritization judgments, not measured or predicted scores. Where the consult could not confirm a license, a weights download or a code release, it says so, and so do we.
>
> **Our additions** are marked **[FaceTrue note]**. Everything else summarizes the consult. The consult itself listed no URLs; the links in the tables were added by us (checked 2026-10-30).

Measured results are in the [technical report](TECHNICAL_REPORT.md). The experiments we chose are in the [improvement plan](IMPROVEMENT_PLAN.md).

## Contents

1. [Summary](#1-summary)
2. [Node semantics: `frame_idx = -1`](#2-node-semantics-frame_idx--1-means-different-things-in-two-nodes)
3. [Top 8 candidates](#3-top-8-candidate-methods)
4. [Three experiments for the next 8 hours](#4-three-experiments-for-the-next-8-hours)
5. [Combinations](#5-can-methods-be-combined)
6. [Other literature](#6-other-literature-why-it-cannot-be-used-right-away)
7. [In-loop options](#7-options-inside-the-diffusion-loop)
8. [Michelle](#8-why-michelle-improves-less)
9. [Evaluation](#9-evaluation-keep-sface-add-temporal-motion-and-quality-checks)

## 1. Summary

For the remaining ~8 hours the consult recommends testing, in order:

1. Verify the LTX reference input path.
2. A pose-matched keyframe generated with the reference photo.
3. Weak reference-only guidance.

Switching to a new video backbone, or training a new single-photo LTX identity LoRA, is deprioritized.

Extra mean gain needed over the current correct-photo result to reach the bar (mean correct − none ≥ +0.12):

| Seed | Current c−n | Extra needed |
|---|---|---|
| 42 | +0.092 | +0.028 |
| 7 | +0.064 | +0.056 |

The consult flags the seed-7 gap as not small.

## 2. Node semantics: `frame_idx = -1` means different things in two nodes

| Node | Meaning of `frame_idx = -1` in current official code | Implication for FaceTrue |
|---|---|---|
| ComfyUI core `LTXVAddGuide` | Counted back from the end; in a 97-frame clip it resolves to frame 96 | The photo guide is tied to the last output frame |
| Lightricks `LTXAddVideoICLoRAGuide` | Kept negative (`if frame_idx < 0: return frame_idx`): RoPE position −1, before the clip | The photo is a reference separate from any output frame |
| `LTXAddVideoICLoRAGuideAdvanced` | Same negative handling, plus separate attention strength and mask | The reference's attention contribution can be tuned on its own |

The official Restore model card uses a second `LTXAddVideoICLoRAGuide` with `frame_idx = -1` and strength 1.0 for the photo. The consult's reading: if the node name in our description was shorthand, there may be no problem; if the photo really goes through generic `LTXVAddGuide`, that is worth testing before installing anything new. Our 0/24/48/72/96 placements were all inside the clip, so they are not the same as an outside-clip −1 reference.

**Three different "strengths".** Core ComfyUI has a path that amplifies reference attention, but the Lightricks Advanced node's `attention_strength` UI maximum is still 1.0, so "already max" can be true for that node. Keep apart:

1. Restore LoRA weight
2. Noise / conditioning strength of the guide latent
3. Attention weight of the photo reference

Our failed LoRA 1.25 / 1.5 runs tested (1), not (3). Raising a UI limit alone should not be assumed to help: `guide_attention_entries` must actually reach the attention computation.

### Status in this repo [FaceTrue note]

- Our workflow already feeds the photo through **`LTXAddVideoICLoRAGuide`, `frame_idx = -1`, strength 1.0** (`workflows/restore.api.json`, node `14`), matching the official Restore model card. The degraded video enters through node `12` (`LTXAddVideoICLoRAGuide`, `frame_idx = 0`).
- So the consult's top hypothesis (a negative index counting back from the end and tying the photo to the last frame) **does not apply**.
- The extra keyframe / chaining guide in `app/workflow.py` uses `LTXVAddGuide` at `frame_idx = 0`. That in-clip position is intended: it pins the first frame of a window.
- The consult's fallback for an already-correct wiring, the photo attention mask, is experiment A in the improvement plan.

## 3. Top 8 candidate methods

Hours are engineering estimates for install, wiring and a small screening run; the final 3 people × 2 seeds × 3 arms run is extra. Code and checkpoint licenses are listed separately: an Apache-2.0 codebase does not lift restrictions on a face encoder or checkpoint.

| # | Method | Core idea | Code / weights | License | LTX / ComfyUI fit | Expected value · effort |
|---|---|---|---|---|---|---|
| 1 | Official LTX IC reference path + photo attention mask | Photo at the outside-clip reference position; reduce the gray canvas's attention contribution | Existing code and weights | Existing LTX Community License | Direct; check actual node and version | Highest value per hour if wiring differs; may be small if already correct. 0.5–1.5 h |
| 2 | Qwen-Image-Edit-2511 → pose-matched keyframe → LTX ([model](https://huggingface.co/Qwen/Qwen-Image-Edit-2511), [ComfyUI](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511)) | Condition on the target frame's pose/expression and the photo's identity together | Official code and weights; native ComfyUI workflow | Apache-2.0 | Image preprocessing step, not an LTX adapter | New identity-correct keyframe candidate; restoration effect unmeasured. 1–2.5 h; stop if download is the bottleneck |
| 3 | Reference-only CFG (small implementation, §4) | On the same noisy latent, weakly amplify only the prediction difference with vs. without the photo | No new checkpoint | Existing LTX terms | Custom sampler / model wrapper; no backward | Low extra compute; untested with distilled Restore. 1–2 h. Motivated by ST-DRC; do not expect its paper results |
| 4 | InstantRestore, SIGGRAPH 2025 ([paper](https://arxiv.org/abs/2412.06753), [code](https://github.com/snap-research/InstantRestore)) | Single-step SD-Turbo restoration; degraded query uses reference K/V; AdaIN and landmark attention control transfer | Official code and final checkpoint; single reference supported | Checkpoint CC-BY-NC-4.0; no separate clear grant for the code found | Keyframe or face-crop post-process; not an LTX adapter | Most promising research-only image candidate; temporal consistency must be solved separately. ≤1–2 h |
| 5 | ReF-LDM, NeurIPS 2024 ([project](https://chiweihsiao.github.io/refldm.github.io/), [code](https://github.com/ChiWeiHsiao/ref-ldm)) | CacheKV computes reference K/V once; timestep-scaled identity loss | Code and checkpoint links public | Model and dataset non-commercial research only | External keyframe / post-process; CacheKV cannot be ported into LTX as is | Good problem fit but costly install and repeated inference. 2–4 h; second choice this time |
| 6 | RG-FVR / RGFVR, 2026 ([paper](https://arxiv.org/abs/2606.16401), [code](https://github.com/batuhanntosun/RG-FVR)) | Perceptual + descriptive identity conditioning on Wan 1.3B; 50-step and 3-step DMD paths | Code public; weights linked, actual download not confirmed | Overall license not confirmed; depends on external models such as antelopev2 | Different video pipeline; not an LTX adapter | Very well suited to the research problem, but release and environment must be verified first; excluded from this 8 h run |
| 7 | Stand-In, CVPR 2026 | Small identity branch, restricted attention and position mapping added to Wan; combinable with VACE etc. | Code and weights public | Code and adapter Apache-2.0; official path uses antelopev2 | Wan ComfyUI wrapper exists; incompatible with LTX | Reference model for combination research; excluded because of backend switch and motion-preservation checks |
| 8 | FaceMe, AAAI 2025 | Combines ArcFace and CLIP identity features to condition personalized diffusion restoration | Inference code and weights public | Pi-Lab License: non-commercial, with extra face-model conditions | External image step; no direct LTX link | Low priority given RestorerID and InstantID were already tried. 2–4 h |

If commercial use comes first, items 1–3 are the default path. InstantRestore and ReF-LDM should be treated as research-comparison candidates only.

**[FaceTrue note]** on row 6: the mediaTUM page for the RGFVR checkpoints lists Apache-2.0, but they bundle the AntelopeV2 ArcFace face encoder, which is non-commercial. We did not use it.

## 4. Three experiments for the next 8 hours

### Budget the final evaluation first

If one full clip for one arm and one seed takes τ minutes, a full evaluation of a new configuration takes about `T_final ≈ 18τ`. At τ = 10 min that is 3 h; at τ = 20 min it is 6 h, and running all three experiments would not fit. Existing no-photo results can be reused only if input, sampler, resolution, tiling and backend are all identical.

Suggested allocation when time allows:

| Time | Work |
|---|---|
| 0:00–0:15 | Record actual node classes, versions, runtime, metric settings |
| 0:15–1:30 | Experiment 1: native reference path |
| 1:30–3:15 | Experiment 2: reference-conditioned keyframe |
| 3:15–4:30 | Experiment 3: weak reference-only CFG |
| 4:30–8:00 | Full evaluation and flicker check of the single best configuration |

Drop experiment 3 first if final evaluation needs more time. If experiment 1 passes, spend the rest on reproducibility and temporal checks.

**[FaceTrue note]** Our τ is about 75 s per render, so `T_final` is about 23 min and all three experiments fit.

### Common acceptance bar

With `I^a_{p,s}` the 13-frame mean SFace for person p, seed s, arm a:

```
Δ_s = (1/3) Σ_p ( I^correct_{p,s} − I^none_{p,s} )
```

Adopt only if all hold:

1. Δ_42 ≥ 0.12 and Δ_7 ≥ 0.12
2. Correct > wrong for every person × seed
3. No visible pop at the first frame or window seams
4. The new correct arm's absolute score beats the old correct arm
5. Lips, blinks and pose are preserved; quality and flicker do not worsen

Rule 4 matters: a larger c−n caused only by a worse no-photo arm is not an improvement.

### Experiment 1: send the photo through the official IC reference path

**Hypothesis:** the bottleneck may be the reference's temporal position and attention routing rather than the photo's identity information.

Steps:

1. Read the photo node's actual `class_type` in the workflow JSON.
2. Check negative-index handling in the installed code; seeing −1 in the UI is not enough.
3. If it is generic `LTXVAddGuide`, switch the photo branch to `LTXAddVideoICLoRAGuide`, `frame_idx = -1`, `latent_downscale_factor = 1`, strength 1.0, `use_streaming = False`.
4. Keep the gray canvas and face-crop placement; do not change crop, color or prompt at the same time.
5. Keep the external 97-frame / 17-overlap chaining and confirm the photo reference is present in every window.
6. Screen Obama and Michelle at seed 42 first; compare correct / wrong, and render matching no-photo if none exists.

**If the node was already correct** (our case), the first alternative is a spatial attention mask on the photo reference: face region 1, gray canvas 0, feathered edge, degraded-video guide unchanged. This mask controls how much the reference tokens are attended to; it is not an inpainting mask on the output.

- Use PyTorch SDPA for the masked path. Current core code avoids the low-precision attention path for guide masks because SageAttention's mask handling is unstable.
- If testing separate attention amplification, change only the photo's metadata strength, to 1.25 and 1.5. That needs a small custom conditioning node. Do not change guide noise strength or Restore LoRA weight at the same time.

Measure: absolute SFace change vs. old correct; c−n and c−w; pose forcing or freezing near the last frame; Michelle's per-frame gains and losses; actual output difference with vs. without the mask.

Stop rules:

- Stop if a working conditioning path is not confirmed within 45 min.
- Do not expand if a 2-person screening gains ≤ +0.01 over old correct with no visible benefit. (+0.01 is a time-boxed screening threshold, not a significance test.)
- Discard immediately if the face turns toward the photo's pose or the mouth freezes.

Also: if sampling is untiled, the officially recommended 960×544 tiles are a candidate, which is different from raising output to 1920. Tiling also changes non-identity quality, so treat it as a separate ablation and re-evaluate all three arms.

**[FaceTrue note]** Our workflow already uses 960×544 spatial tiles (see README), so the tiling suggestion does not add a new experiment.

### Experiment 2: one reference-conditioned keyframe, then check that it propagates

**Hypothesis:** the system can use a good keyframe, but previous keyframe generators could not satisfy target pose and identity at once.

The oracle's +0.196 is not an identity-only ceiling: clean frame 0 also carries exact pose, expression, lighting and camera appearance, which one photo cannot be guaranteed to recover.

**Default choice: Qwen-Image-Edit-2511.** Chosen for its open license and existing ComfyUI path, not because it is a validated reference restorer. The official Comfy-Org repo has `qwen_image_edit_2511_fp8mixed.safetensors` (~20.5 GB). A face-crop job with the text encoder offloaded and LTX not loaded at the same time is worth trying in 32 GB; peak memory and speed must be measured.

Steps:

1. Unload LTX; run only the image model.
2. Prepare a 512–768 px crop around the face in frame 0.
3. Inputs: Image 1 = degraded target frame 0 (pose, expression, mouth shape); Image 2 = the real photo (identity).
4. Fix one image-edit seed and one setting. Start from the official example: 40 steps, true CFG 4.0. Do not add a Lightning LoRA at the same time.
5. Constrain the instruction: *"Restore the facial detail in Image 1 using the identity in Image 2. Preserve the exact head pose, expression, mouth opening, gaze, lighting, and framing of Image 1. Do not beautify the face or change the hairstyle."*
6. Blend the generated crop softly back into frame 0. Do not use it if face position, scale, or eye/nose positions do not line up.
7. Keyframe goes to the frame-0 guide; the real photo stays in the separate IC reference at −1.
8. Start at keyframe strength 0.8. If there is a pop, try 0.6 once; if it persists, discard.
9. Always score the final 97-frame output; a single keyframe passing SFace is not success.

Make a separate keyframe for each arm: none (no photo), correct (correct photo), wrong (wrong photo). Putting the correct keyframe into the wrong arm leaks identity, and c−w ≈ 0 would then not show that the system ignores the photo.

Stop rules:

- Stop if download or compatibility blocks the first crop for more than 45 min.
- Discard if identity improves but the target's mouth shape or gaze changes.
- Do not expand if the final video gains < +0.02 over old correct and the effect fades quickly after the keyframe.
- Any visible pop fails regardless of score.

**Research-only alternative: InstantRestore.** If non-commercial research comparison is allowed, test InstantRestore instead of Qwen, not both. It is single-step and supports one reference, but its official environment pins an old Torch/CUDA combination; do not apply that environment file on an RTX 5090, start from a separate environment that keeps a working Torch. Check: use the final checkpoint; confirm the checkpoint path has `condition_on_face_embeds=False`; check whether only the unused InsightFace initialization can be skipped; do not swap the trained ArcFace embedding for SFace. With InstantRestore, post-processing face crops of the existing LTX output may be cheaper than keyframe propagation (see §5).

### Experiment 3: reference-only guidance without a backward pass

**Hypothesis:** the model already uses the photo, but the prediction difference with vs. without it is not strong enough.

Related paper: ST-DRC (2026), built on LTX-2.3 with reference latents, position separation, identity supervision and independent text/reference CFG. It was trained with 20K full fine-tuning steps and condition dropout; there is no evidence the same principle works on the current Restore model, and its official inference code and checkpoint are still listed as coming soon. What follows is a new engineering heuristic that tests the idea small.

On the same `z_t`, timestep, prompt and degraded-video guide:

```
d_r = D_θ(z_t, t, video, photo)
d_0 = D_θ(z_t, t, video, ∅)
d_guided = d_r + α_t · M_t ⊙ (d_r − d_0)
```

`d` is the denoised prediction in the same parameterization returned by the sampler wrapper; do not mix raw velocity and denoised latents. `M_t` is a soft face-region mask on the output latent. α = 0 reproduces the current photo-conditioned prediction.

Steps:

1. Confirm α = 0 reproduces current results within numerical tolerance.
2. Feed the same noisy target latent to both branches (not two separate videos subtracted afterwards).
3. Compute only over the target-prediction region with guide tokens removed.
4. Keep the existing 8-step schedule.
5. Apply α = 0.25 only at steps 5, 6, 7; the last step uses the normal prediction.
6. If it helps without artifacts, add one more value, 0.5.
7. Run the two forwards sequentially, not batched, to avoid raising peak VRAM.

With a simple Euler path, denoiser calls go from 8 to 11; real time depends on offload and tiling.

Stop rules: stop if α = 0 cannot be verified within 45 min; discard if the gain over old correct is ≤ +0.01; discard if face color is exaggerated, the face is pulled toward the photo's pose, or expression shrinks; do not copy large values such as the paper's reference scale 7.5.

CFG 1 does not rule this out, since it uses the photo / no-photo difference separately from text CFG. But it changes a distilled trajectory, so only a small range should be tested.

## 5. Can methods be combined?

Yes, but gains should not be assumed to add up. Keyframe, reference attention and identity loss can reinforce the same identity information redundantly, and over-reinforcement can damage pose, expression and texture.

| Combination | Value per hour | Key condition |
|---|---|---|
| Correct native reference + photo attention mask | First | Reuses the existing forward; reduces the gray reference's contribution |
| ID-conditioned keyframe + native photo reference | Second | Keyframe must preserve target pose and expression; separate keyframe per arm |
| Native reference + weak reference-only CFG | Third | Only extra forwards; untested on distilled model |
| LTX output + InstantRestore face refinement + temporal residual smoothing | Promising for research | NC license; must prevent the image model's flicker and mouth-motion damage |
| Keyframe + guide + test-time ID gradient | Excluded this time | Adding three things at once makes attribution and memory problems worse |
| Single-photo LoRA + Restore LoRA + guide | Excluded this time | Training fits in 32 GB, but no confirmed few-minute recipe |

### Minimal additivity ablation

Run first for one person at seed 42:

| Condition | Identity keyframe | Photo guide |
|---|---|---|
| I₀₀ | no | no |
| I₁₀ | yes | no |
| I₀₁ | no | yes |
| I₁₁ | yes | yes |

```
interaction = I₁₁ − I₁₀ − I₀₁ + I₀₀
```

Near 0: roughly additive. Negative: redundancy or interference. Positive: possible complementarity. What matters in the end is I₁₁'s absolute identity, quality and motion, more than the sign of the interaction.

### What to smooth in post-hoc refinement

Temporally averaging the whole face blurs lips and eyes. Stabilize only the refinement residual `R_t = F_t^refined − F_t^LTX`: smooth it weakly in motion-aligned coordinates, then add it back to the LTX face. Practical start:

- fixed or stabilized face-crop coordinates
- a short ~3-frame temporal filter
- low smoothing weight on mouth and eyes
- stop carrying the previous residual at occlusions or large pose changes
- also stabilize the composite mask and color-correction parameters over time

InstantRestore can vary between calls even at one step because of VAE sampling and noise. Caching reference K/V once per photo and fixing the noise realization in aligned coordinates are worth testing. These are implementation suggestions to reduce flicker, not video features the paper validated.

## 6. Other literature: why it cannot be used right away

### ID-conditioned video models

"Runs in ComfyUI" is not the same as "an adapter that plugs into LTX". Most of these generate new video and do not by themselves keep the source clip's lips, eyes and pose during restoration.

| Method | Core idea | Code / weights / license | Verdict for this system |
|---|---|---|---|
| ConsisID, CVPR 2025 | Separates low-frequency global face info and high-frequency local identity features, injected into CogVideoX | Public. Code mostly Apache-2.0; transformer under CogVideoX License; extra face-model conditions | Might run in 32 GB with offload; not an LTX adapter, restoration path would need rebuilding |
| Concat-ID, 2025 | Concatenates reference VAE latents to video tokens; CogVideoX and Wan 1.3B / AdaLN versions | Code and model instructions public; overall license not confirmed; Wan install includes InsightFace | Simple structure, but cross-video training is the key; concatenation alone in LTX should not be expected to work |
| MagicMirror, ICCV 2025 | Dual facial embedding, cross-modal adapter, Conditional Adaptive Normalization | Paper and demo exist; official inference code / checkpoint still "coming soon"; license not confirmed | Excluded |
| MAGREF, ICLR 2026 | Masked reference conditioning and subject disentanglement on Wan | Code and weights public; code Apache-2.0; HF checkpoint license not confirmed | Native path needs ~70 GB VRAM; incompatible with LTX; restoration fit unverified |
| Phantom, ICCV 2025 | Learns subject consistency via text-image-video alignment | Wan 1.3B and 14B code / weights public; Apache-2.0 | Relatively good license, but it is reference-to-video generation, not a motion-preserving restorer |
| Lynx, CVPR 2026 | ArcFace-based ID-adapter plus a Ref-adapter for dense reference features | Code and checkpoints Apache-2.0; external ArcFace weights have their own terms; Full and Lite released | Full explicitly needs FlashAttention; Wan 14B backend and install burden rule it out under wheels-only, 8 h |
| HunyuanCustom, 2025 | Text-image fusion, temporal image concatenation, audio/video conditioning on HunyuanVideo | Code and weights public; Tencent Hunyuan Community License | Separate backend; that license's territory excludes South Korea, so not recommended as a default candidate |

Stand-In is in the top table. Stand-In + VACE is a useful research direction for handling identity and motion together, but moving it to LTX is a separate adapter-training and integration job.

### Face restoration models

| Method | Core, release status, license | Verdict |
|---|---|---|
| IP-FVR / Show and Polish, 2025 | Reference attention on VEnhancer, identity-feedback training, overlap blending for long videos. Official repo is mostly assets / README; code and checkpoint are TODO | Paper experiments use paired LQ/HQ video of four different scenes per person and 100-step personalization on an A800. Not a training-free single-photo method; identity feedback is training-time |
| RestorerID, 2024 | StableSR-style restoration with FaceID and an FIR-Adapter. Code and weights public; repo Apache-2.0 with extra FaceID / InsightFace conditions | A reference-conditioned model, not a blind restorer. Since it already failed for us, the useful question is where the reference effect is lost (keyframe stage vs. LTX propagation), not reinstalling it |
| DMDNet, TPAMI 2023 (online 2022) | Generic and person-specific facial dictionaries. Code and weights public; CC-BY-NC-SA-4.0 | Light external crop-processing candidate, but sensitive to landmark and pose correspondence. A 1–2 h probe is possible; low priority |
| ASFFNet512 (original CVPR 2020) | Reference selection, alignment, adaptive spatial feature fusion. Code and weights public; CC-BY-NC-SA-4.0 | Earlier than the requested window; external image step only; behind DMDNet |
| RestoreFormer++, 2023 | Blind restoration with K/V from an HQ codebook and full-spatial attention. Code and weights public; repo Apache-2.0 | The HQ K/V is not a personal photo reference; likely to repeat the blind-restorer failure rather than raise correct − wrong |
| RefSTAR, AAAI 2026 | Reference selection mask, feature transfer and reconstruction. Code and weights links public | Overall license unclear; depends on Arc2Face / antelopev2; cannot be recommended as a clear commercial route |
| IConFace, 2026 | Dense degraded / reference tokens with fine-grained identity and structure conditioning | The paper exists, but HF access returned 401 and no usable checkpoint or license could be confirmed; no install time allocated |

### LTX-related findings

- **Official ID-LoRA:** despite the name, its new conditioning is centered on voice identity; faces use first-frame conditioning. Not an adapter that fills our missing face-identity encoder.
- **Official Ingredients IC-LoRA:** for reference-sheet-based character consistency. Public, but no confirmed recipe for stacking it with Restore. Mixing the degraded video and a reference sheet into the same control input is not recommended.
- **Community LTX-Best-Face-ID:** a real LoRA with ComfyUI nodes, but for LTX-2.3, weight license "other", and untested with LTX-2.5 Restore. Distinct from the official ST-DRC implementation.
- **BFS-Best-Face-Swap-Video:** a real LTX-2.5 checkpoint exists, but it targets head swapping, so preservation of the source's facial micro-motion must be verified separately, and its model card requires explicit consent from the people processed. Not added as a default path for the three public-domain clips.

## 7. Options inside the diffusion loop

### Identity gradient: sound in principle, costly now

FreeDoM (ICCV 2023) and Universal Guidance (2023) are real work on steering diffusion with an external energy or recognition objective; that does not mean there is a ready LTX-2.5 implementation. Conceptually:

```
L_ID = 1 − cos( E(C(D(ẑ₀))), E(C(r)) )
```

with D the VAE decoder, C face crop and alignment, E an identity encoder, r the reference photo. The bottleneck is the differentiation path, not the formula:

1. OpenCV SFace calls are not connected to PyTorch autograd. A gradient needs a differentiable floating-point implementation with verified preprocessing parity; SFace is distributed as ONNX.
2. The exact gradient includes the large DiT's Jacobian. INT8 inference working does not mean backward is supported on the same path.
3. Detaching the DiT gives a different heuristic. A clean-latent correction that differentiates only the VAE is possible, but must be distinguished from exact full-model guidance.
4. Reconstructed faces at early steps may be unsuitable for a recognizer. ReF-LDM reports that applying identity loss to one-step predictions at large timesteps can hurt quality, and down-weights it in training.

So native attention or two-forward reference guidance is more realistic this time.

### Other training-free options

| Option | Verdict |
|---|---|
| Native reference attention mask / weight | Most realistic; no extra identity model or backward |
| Porting reference attention / K/V injection from another model | Not a simple port: CacheKV and IP-Adapter projections, layers, RoPE and training distribution differ |
| Face-region latent blending | Needs matching pose, noise level and temporal coordinate; blending a static photo latent risks the pop and frozen face we already saw |
| Seed search | Easy, but cost grows linearly; best-of-N cannot be reported as an improvement at fixed seeds 42 / 7 |
| Initial-noise gradient optimization | Needs repeated differentiation of the whole sampling graph; unsuitable for this time limit |
| Late-step decoder-only correction | Possible as research, but VAE / encoder wiring keeps it out of the top 3 |

### Is a single-photo LoRA impossible in 32 GB?

Saying it is impossible for memory reasons is inaccurate: the current official LTX trainer documents an RTX 5090 32 GB LoRA path with INT8, an 8-bit optimizer and reduced rank. What is unverified is the claim that a few minutes of training on one photo adds identity gains on top of the Restore LoRA and distilled 8-step sampling. One photo makes it hard to separate identity from pose, lighting and background, and interference with the Restore LoRA must be checked. Unless a trainer and a validated config are already installed, the consult would not start training in this window.

## 8. Why Michelle improves less

The consult reads "Michelle never improves" as: no variant beats the existing photo baseline for her. If it meant correct − none never improves, that conflicts with +0.031 and 76/78 frames, and the raw results should be rechecked. 0.773 is not a mathematical ceiling, but the remaining 0.227 is not all recoverable identity either.

| Hypothesis | Diagnosis available now | Action |
|---|---|---|
| No-photo already preserves identity well | Correct vs. none by person and pose | Keeping the current result may beat overwriting with stronger conditioning |
| Pose / age / lighting / makeup gap between photo and clip | Reference ↔ clean-frame cosine split by yaw and expression | Pick a photo from a similar time and pose rather than adding more photos |
| Reference tied to one output time | Check node class and resolved temporal coordinate | Switch to outside-clip IC reference (**already the case** [FaceTrue note]) |
| Face tokens weak vs. gray canvas | Test the photo attention mask | Adjust only the face reference tokens' contribution |
| SFace alignment / crop sensitivity | Same-crop scoring vs. standard per-frame alignment | Fix crop, color order or landmark errors |
| Genuine model failure | Second recognizer and by eye | Keep as an unsolved case; don't call it a ceiling |

GPU-free checks first: (1) cosine distribution of Michelle's reference vs. the 13 clean frames; (2) her clean frame 0 vs. the other clean frames; (3) existing c−n split by yaw, mouth opening and brightness. Gains only on pose-similar frames support reference mismatch. Small changes everywhere with a good no-photo result suggest strong identity overwriting may hurt.

Wrong ≈ none is not necessarily a failure: the model may be rejecting a reference that conflicts with the video. The goal is higher real fidelity for the correct photo, not making the wrong-photo result look more like someone else.

## 9. Evaluation: keep SFace, add temporal, motion and quality checks

The 13-frame SFace metric is a good start: clean GT, same-seed paired comparison, none / correct / wrong controls, three different people. It is not enough alone to judge final quality.

| Priority | Check | Purpose |
|---|---|---|
| 1 | Existing SFace metric unchanged | Comparability with earlier results |
| 2 | Motion-compensated flicker on all frames or seam regions | Catch pops and texture flicker 13 samples miss |
| 3 | Face-crop LPIPS + mouth / eye / pose trajectories | Catch identity gains that change expression or freeze the face |
| 4 | One independent recognizer | Check for SFace-specific overfitting |
| 5 | No-reference quality metric | Secondary, for real archive footage with no clean GT |

With clean GT available, LPIPS and motion fidelity come before no-reference quality. A standalone LPIPS implementation is public.

**Do not measure flicker with raw frame differences**; they penalize normal talking. Apply the flow and occlusion mask computed on the clean clip X to every arm Y:

```
e_t^Y  = Y_t − W(Y_{t−1}, F_t^X)
e_t^X  = X_t − W(X_{t−1}, F_t^X)
E_temp = mean_t || M_t ⊙ (e_t^Y − e_t^X) ||_1
```

With 97-frame windows and 17-frame overlap the stride is 80: check global frames 80–96, 160–176 and around each seam densely. Track mouth opening, blinks and pose so a frozen face does not score well.

**ArcFace or AdaFace?** Adding one as an independent evaluator is good, but should not delay the core experiments. ArcFace is a method name and checkpoints differ in license. InsightFace code is MIT, but its pretrained weights are non-commercial research only. AdaFace code being MIT does not make its checkpoints commercially free; the official HF model defers to its training-data license. Use a checkpoint permitted for research evaluation, and keep the selection / optimization metric separate from the final confirmation metric. Choosing seeds or hyperparameters by SFace and then reporting only an SFace rise is weak evidence.

**Evaluation errors to avoid**

- Do not treat 78 frames as 78 independent samples; there are three people / clips.
- Do not silently drop frames where detection failed.
- Use a macro average weighting each person equally.
- Report correct − wrong separately per person and per seed.
- Record how the wrong-photo control was built; if it differs a lot in gender or pose, the model can use easy cues instead of identity.
- Do not report keyframes or seeds picked by looking at clean GT as general single-photo performance.
- Do not let a keyframe or cached feature made from the correct photo leak into the no-photo arm.

**Operational reject rule** (set for this experiment, not a universal threshold from the literature): after a visual re-check, reject if face LPIPS worsens by ≥ 0.02 vs. old correct, or motion-compensated temporal error rises by ≥ 10%.

If the final configuration does not pass +0.12 at both seeds, correct > wrong for all three people, and no pop, keep the baseline. The most useful output then is not "the new method looked good" but a record isolating where the gain is lost: reference input, keyframe generation, or identity propagation.
