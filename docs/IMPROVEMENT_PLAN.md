# Improvement plan: final identity experiments (2026-10-30)

This plan turns the [research notes](RESEARCH_NOTES.md) into a short list of experiments. Measured results so far are in the [technical report](TECHNICAL_REPORT.md).

## 0. Facts confirmed before planning

- The photo already uses the official path: `workflows/restore.api.json` node `14`, `LTXAddVideoICLoRAGuide`, `frame_idx -1`, strength 1.0. The consult's top hypothesis (a generic `LTXVAddGuide` with `-1` tying the photo to the last frame) does not apply.
- The extra keyframe / chaining guide in `app/workflow.py` is `LTXVAddGuide` at `frame_idx 0`. That is an in-clip position and is intended.
- One render takes about 75 s, so a full evaluation of one new configuration (3 people × 2 seeds × 3 arms = 18 renders) takes about 23 minutes. All three experiments fit.

## 1. Acceptance bar (all must hold to adopt a change)

1. Mean correct − none ≥ +0.12 at **both** seed 42 and seed 7 (currently +0.092 / +0.064).
2. Correct > wrong for every person at every seed.
3. No pop at the first frame or at window seams; mouth and eye motion preserved.
4. The absolute correct-arm score must rise. A gain that comes only from a worse no-photo arm is not an improvement.
5. Reject if face LPIPS worsens by 0.02 or more.

## 2. Experiments, in order

| Step | Experiment | What it does | Stop rule |
|---|---|---|---|
| M | Michelle diagnosis (no GPU) | Similarity of Michelle's photo to the 13 clean frames; gain broken down by pose and expression | — |
| A | Photo attention mask | Use `LTXAddVideoICLoRAGuideAdvanced` with the photo's face region at 1 and the gray background at 0 (soft edge). First check the node is installed. | Stop if it can't be made to work within 45 min. Don't expand if a 2-person screening gains ≤ +0.01. |
| B | Photo-aware keyframe (Qwen-Image-Edit-2511, Apache-2.0) | Degraded frame 0 (for pose) + photo (for identity) → new frame 0 → LTX keyframe at strength 0.8. Generate separately for none / correct / wrong arms. | Stop if download or compatibility takes more than 45 min. Discard if mouth or gaze changes. Reject on any pop. |
| C | Reference-only guidance (if time remains) | Amplify the photo / no-photo prediction difference by 0.25× on steps 5–7 | Stop if α = 0 can't reproduce the baseline within 45 min. |
| Decision | — | Adopt anything that passes the bar; otherwise keep the current version. | — |

For any pair of changes that both pass screening, run the 2×2 interaction check described in the research notes before combining them.

## 3. Not in scope for this round

- Switching to a new video backbone (Wan family and similar).
- Training a single-photo LoRA.
- Adopting non-commercial models: InstantRestore, ReF-LDM, CodeFormer, antelopev2.
