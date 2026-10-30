# Research notes: external literature review (2026-10-30)

> **What this is.** A summary of an external research consult (a literature and code review requested on 2026-10-30). It is **not** a set of results we ran. The consult read papers, official repositories, model cards and node source code. It did not install or run any of these methods on our GPU.
>
> **Caveats kept from the consult.** "Expected gain" columns are prioritization judgments, not measurements. ArcFace numbers reported in papers cannot be converted into SFace gains on our three clips. Where the consult could not confirm a license or a weights download, it says so, and so do we. Reaching the acceptance bar is not guaranteed.
>
> **Scope of this summary.** The copy of the consult available when this file was written was partly truncated. The ranked table, the node analysis, the Michelle section and the evaluation section are summarized in full. The combination, in-loop and broader literature sections are condensed, and rows we could not read in full are marked.

Our measured results are in the [technical report](TECHNICAL_REPORT.md). The experiments we chose from this review are in the [improvement plan](IMPROVEMENT_PLAN.md).

## 1. Summary of the consult

For the remaining ~8 hours on one RTX 5090, the consult recommended testing, in order:

1. Verify the LTX reference input path (which node and which `frame_idx` semantics the photo uses).
2. A pose-matched keyframe generated from the reference photo.
3. Weak reference-only guidance inside the sampler.

It recommended **not** switching to a new video backbone and **not** training a single-photo LTX identity LoRA in this window.

Gap to the acceptance bar (mean correct − none ≥ +0.12 at both seeds), relative to our current correct-photo result:

| Seed | Current c−n | Extra gain needed |
|---|---|---|
| 42 | +0.092 | +0.028 |
| 7 | +0.064 | +0.056 |

The consult noted that the seed-7 gap is not small.

## 2. Node semantics: `frame_idx = -1` means different things in two nodes

| Node | Meaning of `frame_idx = -1` in current official code | Implication |
|---|---|---|
| ComfyUI core `LTXVAddGuide` | Counted back from the end of the clip. In a 97-frame clip it resolves to frame 96. | The photo guide is tied to the last output frame. |
| Lightricks `LTXAddVideoICLoRAGuide` | Kept as a negative position (`if frame_idx < 0: return frame_idx`), i.e. RoPE position −1, before the clip. | The photo acts as a reference outside any output frame. |
| `LTXAddVideoICLoRAGuideAdvanced` | Same negative handling, plus a separate attention strength and attention mask. | The reference's attention contribution can be tuned on its own. |

The official Restore model card uses a second `LTXAddVideoICLoRAGuide` with `frame_idx = -1` and strength 1.0 for the photo reference.

The consult also separated three different "strength" variables that are easy to conflate:

1. Restore LoRA weight (our 1.25 / 1.5 ablations tested only this).
2. Noise / conditioning strength of the guide latent.
3. Attention weight of the photo reference tokens.

The Advanced node's `attention_strength` UI maximum is 1.0. Raising a UI limit only helps if the value actually reaches the attention computation (`guide_attention_entries`). Our 0/24/48/72/96 guide placements were all inside the clip, so they are not the same experiment as an outside-clip −1 reference.

### Status in this repo

- Our workflow already feeds the photo through **`LTXAddVideoICLoRAGuide` with `frame_idx = -1` at strength 1.0** (`workflows/restore.api.json`, node `14`). This matches the official Restore model card. The degraded video itself goes through node `12` (`LTXAddVideoICLoRAGuide`, `frame_idx = 0`).
- So the consult's top hypothesis (that a negative index counts back from the end and ties the photo to the last frame) **does not apply** to us.
- The extra keyframe / chaining guide in `app/workflow.py` uses `LTXVAddGuide` at `frame_idx = 0`. That is an in-clip position on purpose: it pins the first frame of a window.
- What remains open from item 1 is the **attention mask** variant (Advanced node, photo face region weighted 1, gray canvas 0). That is experiment A in the plan.

## 3. Top 8 candidate methods (ranked by the consult)

Hours are engineering estimates for install, wiring and a small screening run. A full 3 people × 2 seeds × 3 arms evaluation is extra. "Open" separates code from checkpoints: an Apache-2.0 codebase does not lift restrictions on a face encoder or checkpoint.

| # | Method | Core idea | Code / weights | License | Fit with LTX / ComfyUI | Expected gain · effort |
|---|---|---|---|---|---|---|
| 1 | Official LTX IC reference path + photo attention mask | Put the photo at the outside-clip reference position and reduce the gray canvas's attention contribution | Existing code and weights | LTX Community License (existing) | Direct; check node version | Highest value if wiring differs; small if already correct (it is, see above). 0.5–1.5 h |
| 2 | [Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) → pose-matched keyframe → LTX | Condition on the target frame's pose/expression and the reference's identity to make a keyframe | Official code and weights; native [ComfyUI workflow](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511) | Apache-2.0 | Image preprocessing step, not an LTX adapter | New identity-correct keyframe candidate; restoration effect unmeasured. 1–2.5 h; stop if the download is the bottleneck |
| 3 | Reference-only CFG (small custom implementation) | On the same noisy latent, amplify only the prediction difference between photo and no photo, weakly | No new checkpoint | Existing LTX terms | Needs a custom sampler / model wrapper; **no backward pass** | Low extra compute; untested with distilled Restore. 1–2 h. Motivated by ST-DRC; paper results should not be expected to transfer |
| 4 | InstantRestore, SIGGRAPH 2025 ([paper](https://arxiv.org/abs/2412.06753), [code](https://github.com/snap-research/InstantRestore)) | Single-step SD-Turbo restoration; degraded query attends to reference K/V; AdaIN and landmark attention control transfer | Code and final checkpoint public; single reference supported | Checkpoint CC-BY-NC-4.0; a separate clear grant for the code could not be confirmed | Keyframe or face-crop post-process; not an LTX adapter | Most promising new research image candidate; temporal consistency must be solved separately. ≤1–2 h |
| 5 | ReF-LDM, NeurIPS 2024 ([project](https://chiweihsiao.github.io/refldm.github.io/), [code](https://github.com/ChiWeiHsiao/ref-ldm)) | CacheKV: compute reference K/V once; timestep-scaled identity loss | Code and checkpoint public | Model and dataset non-commercial research only | External keyframe / post-process; CacheKV cannot be ported to LTX as is | Good problem fit but costly install and repeated inference. 2–4 h; second choice |
| 6 | RG-FVR / RGFVR, 2026 ([paper](https://arxiv.org/abs/2606.16401), [code](https://github.com/batuhanntosun/RG-FVR)) | Wan 2.1 1.3B with perceptual + descriptive identity conditioning; 50-step and 3-step DMD paths | Code public; weights linked, download not verified by the consult | Overall license unconfirmed by the consult; depends on external models such as antelopev2 | Different video pipeline; not an LTX adapter | Strong problem fit, but a backbone switch. Excluded for this window |
| 7–8 | *(rows truncated in the copy we had)* | — | — | — | — | — |

Note added by us on row 6: the mediaTUM weights page lists Apache-2.0 for the RGFVR checkpoints, but the face encoder they bundle (AntelopeV2 ArcFace) is non-commercial. We did not use it.

## 4. Combining methods

The consult's position: combinations can add up only if each part attacks a different failure. A good keyframe fixes frame 0; the photo guide carries identity through the window; an in-loop term strengthens the photo's effect at each step. Our own round 2–3 data shows the risk: a photo-blind keyframe locks identity and makes the photo irrelevant (c−w ≈ 0).

So any combination should be tested as a **2×2 factorial**, not stacked blindly. With factors A (e.g. keyframe) and B (e.g. reference-only CFG), each cell measured as mean correct − none at the same seeds:

```
interaction = (G_AB − G_B) − (G_A − G_0)
            = G_AB − G_A − G_B + G_0
```

where `G_0` is the baseline, `G_A` and `G_B` are each change alone, and `G_AB` is both together. A positive interaction means the parts help each other; near zero means they add; negative means one cancels the other. Report c−w for every cell too, so a combination that only raises the no-photo score is not counted as identity gain.

Cost ranking from the consult (gain per hour): reuse existing nodes first (attention mask), then a preprocessing-only keyframe (Qwen), then the sampler change. A per-photo LoRA is the most expensive and was excluded (section 6).

## 5. In-loop (training-free) options

| Option | Status for distilled 8-step, CFG 1 |
|---|---|
| Reference-only CFG: `ε = ε_ref + α (ε_ref − ε_noref)` on a few late steps | Realistic. Forward passes only, no backward. Doubles model calls on the chosen steps. Untested with distilled Restore. |
| Identity-gradient guidance (ArcFace / SFace loss gradient on the decoded face) | Costly. Each guided step needs a VAE decode, a face recognizer, and a backward pass through the 22B transformer. That is hard to fit in 32 GB with INT8 weights, and with only 8 distilled steps there are few steps to correct. It also optimizes the same family of metric we evaluate with. |
| Reference attention injection | Partly covered by the official IC reference path; the Advanced node's mask is the realistic knob. |
| Face-region latent blending | Risky for pops and seams; our pasted-keyframe test already showed a visible pop. |
| Seed / noise search scored by identity | Selecting seeds by an identity score on clean GT is selection bias; not reportable as single-photo performance. |

## 6. Single-photo LoRA (excluded)

The consult would not start training in this window unless a trainer and a validated config were already installed. One photo cannot separate identity from pose, lighting and background, and interference with the Restore LoRA would have to be checked. The open question it would answer: "Does a short identity LoRA add identity improvement on top of distilled 8-step sampling?"

## 7. Why Michelle improves less

"Michelle never improves" is read as: no variant beats the existing photo baseline for her. Her correct − none itself is positive (+0.031). 0.773 (her no-photo score) is not a mathematical ceiling, but the remaining 0.227 is not all recoverable identity either.

| Hypothesis | Diagnosis available now | Action depending on result |
|---|---|---|
| No-photo already preserves identity well | Break down correct vs none per person and per pose | Keep the current result rather than overwrite with stronger conditioning |
| Pose / age / lighting / makeup gap between photo and clip | Decompose reference ↔ clean-frame cosine by yaw and expression | Choose a photo from a similar time and pose instead of adding more photos |
| Reference tied to one output time | Check node class and resolved temporal coordinate | Use outside-clip IC reference (**already the case**, section 2) |
| Face tokens weak relative to the gray canvas | Test a photo attention mask | Adjust only the face reference tokens' contribution |
| SFace alignment / crop sensitivity | Compare same-crop scoring with standard per-frame alignment | Fix crop, color order or landmark errors |
| Genuine model failure | Check a second recognizer and by eye | Keep as an unsolved case; do not call it a ceiling |

Three GPU-free checks first:

1. Cosine distribution between Michelle's reference and the 13 clean frames.
2. Cosine distribution between her clean frame 0 and the other clean frames.
3. Existing correct − none split by yaw, mouth opening and brightness.

If gains appear only on pose-matched frames, reference mismatch is the likely cause. If gains are small everywhere and no-photo is already good, strong identity overwriting may hurt.

Wrong ≈ none is not necessarily a failure. The model may be rejecting a reference that conflicts with the video. The goal is higher real fidelity for the correct photo, not making the wrong-photo result look more like someone else.

## 8. Evaluation recommendations

Keep SFace on 13 frames vs. clean as the primary metric (clean GT, same-seed paired arms, no-photo / correct / wrong controls, three people). It is a good start, but not enough on its own.

| Priority | Check | Purpose |
|---|---|---|
| 1 | Existing SFace metric, unchanged | Comparability with earlier results |
| 2 | Motion-compensated flicker on all frames, dense around window seams | Catch pops and texture flicker that 13 samples miss |
| 3 | Face-crop LPIPS + mouth / eye / pose trajectories | Catch identity gains that change expression or freeze the face |
| 4 | One independent recognizer | Guard against SFace-specific overfitting |
| 5 | No-reference quality metric | Secondary, for real archive footage with no clean GT |

**Flicker must be motion-compensated.** Raw adjacent-frame differences penalize normal talking. Use flow `F_t^X` and occlusion mask `M_t` computed on the clean clip `X`, and apply them to every arm `Y`:

```
e_t^Y  = Y_t − W(Y_{t−1}, F_t^X)
e_t^X  = X_t − W(X_{t−1}, F_t^X)
E_temp = mean_t || M_t ⊙ (e_t^Y − e_t^X) ||_1
```

With 97-frame windows and 17-frame overlap the stride is 80, so check global frames 80–96, 160–176 and each seam densely. Also track mouth opening, blinks and pose so a frozen face does not score well.

**Independent recognizer.** Add one, but do not let it delay the core experiments. ArcFace is a method name; checkpoints differ in license. InsightFace code is MIT, but its pretrained weights are non-commercial research only. AdaFace code being MIT does not make its checkpoints commercially free; the official HF model defers to its training-data license. Use a research-permitted checkpoint for evaluation only, and keep the metric used for selection separate from the metric used for final confirmation.

**Pitfalls to avoid**

- Do not treat 78 frames as 78 independent samples. There are three people / clips.
- Do not silently drop frames where detection failed.
- Use a macro average that weights each person equally.
- Report correct − wrong per person and per seed.
- Record how the wrong-photo control was chosen. If it differs in gender or pose, the model can separate it by easy cues instead of identity.
- Do not report keyframes or seeds chosen by looking at clean GT as general single-photo performance.
- Make sure no correct-photo keyframe or cached feature leaks into the no-photo arm.

**Operational reject rule** (set for this experiment, not a universal threshold from the literature): reject after visual re-check if face LPIPS worsens by 0.02 or more vs. the current correct arm, or motion-compensated temporal error rises by 10% or more.

If no configuration passes the +0.12 bar at both seeds, correct > wrong for all three people, and no visible pop, keep the baseline. The most useful output then is a record that isolates where the gain is lost: reference input, keyframe generation, or identity propagation.

## 9. Other literature (compressed)

These were listed in the consult's question set and reviewed at a higher level. Details below are short; licenses that are not stated here were not confirmed.

**ID-conditioned video generators** (ConsisID, Concat-ID, MagicMirror, MAGREF, Phantom, Stand-In, Lynx, HunyuanCustom). They inject identity into text/image-to-video generation, usually on other backbones (Wan, HunyuanVideo, CogVideoX) and often with face encoders such as antelopev2. They are generators, not restorers, and none plugs into LTX-2.5 directly. Verdict: excluded for this window (backbone switch).

**Reference-based face restoration** (IP-FVR, RG-FVR, RestorerID, InstantRestore, ReF-LDM, FaceMe, DMDNet, ASFFNet, RestoreFormer++). Video methods (IP-FVR, RG-FVR) use their own pipelines; image methods can only act as keyframe or per-frame post-processors and then need temporal smoothing. Several carry non-commercial checkpoints. RestorerID was already tested by us (worse than baseline, technical report §6.2).

**LTX-related LoRAs and nodes.** The relevant pieces are the Lightricks Restore IC-LoRA (already used) and the IC-LoRA guide nodes, including the Advanced variant with an attention mask. No ready-made LTX identity LoRA was identified as a drop-in.
