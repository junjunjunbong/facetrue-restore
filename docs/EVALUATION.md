# Evaluate whether a separate photo helps

This script makes a reproducibly degraded input from a clean clip, renders **without a photo / with the correct photo / with a different person's photo**, and compares all outputs against the corresponding clean frames. It reports the measured values even when the photo hurts the result.

The score is an identity diagnostic. It does not establish that generated details are historically accurate. Three clips constitute a pilot, not general evidence of reliable identity restoration. No scores have been prefilled in this repository.

## Inputs

Use one person with fixed framing, at most ten seconds, and an independent photograph. A photograph extracted from the target clip is not an independent reference. The operator must establish which person appears in each photo. The script does not identify unknown archival people.

Keep the clean clips, photographs, manifest, model weights, and output under gitignored local directories. Obtain permission to use personal material. For public material, record the exact item license; a collection name alone does not establish reuse rights.

Example `data/evaluation/pilot.json` (paths are relative to the manifest):

```json
{
  "version": 1,
  "seed": 42,
  "steps": 8,
  "width": 1280,
  "height": 736,
  "fps": 24,
  "frame_count": 97,
  "sample_every": 8,
  "min_common_coverage": 0.8,
  "clips": [
    {
      "id": "pilot-a",
      "hq_video": "subject-a-hq.mp4",
      "reference": "subject-a-separate-photo.jpg",
      "wrong_reference": "subject-b-separate-photo.jpg",
      "identity_id": "subject-a",
      "wrong_identity_id": "subject-b",
      "independent_reference_confirmed": true,
      "reference_origin": "Separately photographed portrait; not an exported video frame",
      "source_rights": "Replace with actual permission or exact source/license URL",
      "face_bbox": {"x": 500, "y": 150, "width": 220, "height": 260}
    }
  ]
}
```

Replace every source description with an accurate record. Add three or more clips with different identities when available. `face_bbox` is measured on the normalized output canvas in **pixels**, with origin at its top-left. It is not a fractional bbox. Normalization preserves aspect ratio and pads the remaining area black. Choose the same placement for both photo conditions.

The correct and wrong photo normally must each contain exactly one detectable face. Optional `reference_bbox` and `wrong_reference_bbox`, also `{x,y,width,height}` pixels, can select one person in their respective EXIF-oriented photos. A valid face must still be detectable inside the selected crop for scoring. No-face and ambiguous-face cases are not assigned fabricated similarity values.

`frame_count: 49` and `frame_count: 97` are convenient hardware preflights. The clean input must contain enough frames after fps normalization. The default chunked runner supports longer clips within the app limit. `--direct` bypasses chunking and only accepts 49 or 97 frames.

## Install optional evaluation models explicitly

The app never downloads an evaluation model during import, upload, or scoring. The following command downloads the two official OpenCV Zoo ONNX files and their license texts, then checks pinned SHA256 hashes. Model weights remain outside git.

```bash
python scripts/download_eval_models.py
```

| File | Bytes | SHA256 |
|---|---:|---|
| `face_detection_yunet_2023mar.onnx` | 232589 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| `face_recognition_sface_2021dec.onnx` | 38696353 | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

Hashes and sizes were read from the upstream Git LFS pointer files. A Git LFS pointer downloaded in place of model bytes fails validation. Use OpenCV 4.x with the 2023mar YuNet checkpoint; the project requirements cap OpenCV below 5.

## Run

Configure the real Comfy connection and required restoration weights first. Mock mode is refused. The output directory must be empty so a new experiment cannot overwrite earlier evidence.

```bash
FACETRUE_MODE=comfy python scripts/evaluate.py data/evaluation/pilot.json \
  --output data/evaluation/run-001
```

For one 49- or 97-frame direct hardware preflight:

```bash
FACETRUE_MODE=comfy python scripts/evaluate.py data/evaluation/pilot.json \
  --output data/evaluation/preflight-001 --direct
```

The run performs these operations for every clip:

1. Normalize the clean HQ source to the requested dimensions, fps, and exact frame count. Encode a clean comparison target with H.264 CRF 10. This normalized target, not the unprocessed source file, defines the metric reference.
2. Downsample by four, apply Gaussian blur (`sigma=1.2`), resize back, and encode H.264 at CRF 32. These operations provide a controlled degradation test; they are not a complete VHS or 8mm physical simulation.
3. Build gray reference canvases from the correct and wrong photographs at the same target bbox.
4. Render all three conditions with the same seed, steps, prompt, input bytes, dimensions and fps. With the chunked adapter, the same per-chunk seed policy must be used in all conditions.
5. Decode every output and fail if frame count, fps, or dimensions differ. It never silently compares different timestamps or trims a failed result to the shortest video.
6. Sample deterministic frame indices and extract a single face using local YuNet + SFace.
7. Compute primary cosine similarity against the clean HQ frame at that index. Affinity to the conditioning photographs is reported separately.
8. Aggregate all arms on exactly the same common valid frame indices and save failures alongside scores.

Reference independence is partly an operator attestation. The script checks different file hashes and rejects an exact decoded match to a sampled normalized target frame. Re-encoding or cropping a leaked frame can evade these checks; a hash cannot prove separate capture or correct identity.

## Outputs and interpretation

- `run.json`: manifest, source/output hashes, model hashes, settings, degradation recipe, per-clip results, failures, and completion state.
- `frames.csv`: every sampled frame and condition, similarity diagnostics, and any detection failure reason.
- `summary.csv`: per-clip/condition means, medians, valid/common-valid counts, coverage, paired deltas, and status.
- Per-clip directories: clean/degraded clips, both reference canvases, and all three actual restored videos.

`correct_minus_without` measures whether the correct photo increases similarity to the clean target. `correct_minus_wrong` checks whether the matched identity helps more than the wrong-person control. Negative values remain in the report. Scores closer to one indicate more similar SFace embeddings; they are not calibrated probabilities or percentages of recovered identity.

A frame that fails in one condition is excluded from the paired mean for every condition. The failure remains visible in counts and `frames.csv`. If common coverage is below `min_common_coverage`, the clip is `inconclusive`. An experiment can finish successfully while a clip remains inconclusive. `pilot_result` means the coverage rule was met; it does not mean restoration improved.

The summary does not perform significance testing by treating adjacent video frames as independent observations. Compare clips/persons as the experimental units. Inspect the synchronized videos for expression changes, geometry, age, flicker and chunk seams before making a quality claim.

All rendered evidence comes from the real backend. An injected test engine is marked `control_flow_test`; unit tests and mock runs establish software behavior only.

## Model licensing and provenance

The app's MIT license does not relicense third-party model weights.

| Model | Official distribution terms | Verification limits |
|---|---|---|
| YuNet 2023mar | MIT; model-directory README applies it to all files | This records upstream's published license, not an independent audit of training data |
| SFace 2021dec | Apache-2.0; model-directory README applies it to all files | Exact training-data provenance: **확인 필요**; upstream questions #313/#318 remain open |

As checked on 2026-10-27, SFace's official README names the contributor and ONNX converter and states that all files in that directory are Apache-2.0. In #318, ShiqiYu referred the requested commercial usage to Apache 2. Follow-up questions about the exact checkpoint's training data remained unanswered in the inspected discussion. This project does not claim complete commercial rights clearance beyond the published upstream terms.

InsightFace's code is MIT, but its README separately restricts the distributed pretrained models to non-commercial research. This evaluator therefore does not auto-download InsightFace's bundled pretrained models or label them MIT.

Authoritative sources actually inspected:

- [YuNet README](https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/README.md), [license](https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE), [weight pointer](https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx).
- [SFace README](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/README.md), [license](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/LICENSE), [weight pointer](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx).
- [OpenCV detection/alignment/embedding tutorial](https://docs.opencv.org/4.13.0/d0/dd4/tutorial_dnn_face.html).
- [SFace provenance issue #313](https://github.com/opencv/opencv_zoo/issues/313), [issue #318](https://github.com/opencv/opencv_zoo/issues/318), [maintainer's response](https://github.com/opencv/opencv_zoo/issues/318#issuecomment-5924130418).
- [InsightFace license policy](https://github.com/deepinsight/insightface/blob/master/README.md#license).

## Demo evidence

Any comparison made with this evaluation input must visibly say **Synthetically degraded test clip** in the published demo/export. Do not describe it as recovered VHS detail. Do not publish mock outputs as restoration results.

The [Prelinger home-movie candidate](https://commons.wikimedia.org/wiki/File:Home_Movies_-_Western_U.S.,_New_Mexico,_Mexico,_California,_Colorado,_Utah.webm) has a file-specific public-domain dedication record, but no verified separate photograph of a depicted person was established for this project. It is a qualitative archival restoration candidate, not the clean-HQ identity benchmark above.
