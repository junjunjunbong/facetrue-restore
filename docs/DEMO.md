# FaceTrue Restore: 2-minute demo plan

**This is a recording script, not a claim that GPU results already exist.** Fill the marked result slots only after a real run passes [GPU_PREFLIGHT.md](GPU_PREFLIGHT.md). Mock videos are useful for UI rehearsal but must not be presented as restored footage. The final video should be at most 120 seconds; aim for 115-118 seconds after recording so the export stays within the limit.

The opening must show a separate actual photograph next to both restoration conditions. The viewer should see the evidence before the setup explanation.

## Recording assets

Prepare these local assets without committing private media or generated video:

- A permitted 4-10 second fixed-framing clip with one person.
- A separate actual photograph of the same person, ideally from a similar period/age. Do not use a target frame as the photo.
- Real `without-photo.mp4` and `with-photo.mp4` from the same input, seed, model configuration and window seed sequence.
- The corresponding original, reference-canvas preview, side-by-side/wipe exports and run manifest.
- A three-clip evaluation report including the wrong-person-photo control and detection coverage, if the evaluation has been completed.
- Exact source and license/permission notes for every visual used in the public recording.

For a synthetic evaluation source, create the displayed comparison through `scripts/restore.py --synthetic` or the UI's test-clip checkbox. Keep the **SYNTHETICALLY DEGRADED TEST CLIP** label visible. The evaluation input is deliberately blurred/downsampled/compressed; it is not a recovered original tape.

## Shot list and spoken script

Times below total 120 seconds. Spoken lines are a draft; trim pauses to reach the shorter export target. Bracketed material is an instruction to the editor, not a claim to leave on screen.

| Time | Picture / action | Suggested Korean narration |
|---|---|---|
| 0-10s | Show the real separate photo at left and synchronized **Without photo / With photo** results together. Freeze briefly on the same frame, then play both. Keep any synthetic label visible. | “같은 영상을 같은 seed로 두 번 처리했습니다. 가운데는 사진 없이, 오른쪽은 이 별도 사진을 넣은 결과입니다. 얼굴이 어떻게 달라지는지 직접 비교할 수 있습니다.” |
| 10-22s | Reveal the original clip alongside the photo. Show provenance and whether degradation was synthetic. | “이 테스트는 [실제 자료 설명]입니다. 참조 사진은 복원 대상 영상에서 잘라낸 프레임이 아니라 따로 촬영한 사진입니다.” If synthetic: “고화질 원본을 일부러 열화해서 비교했습니다.” |
| 22-35s | Record the actual web UI: upload clip and select deinterlacing if appropriate. Show the first frame. | “FaceTrue Restore는 짧은 가족 영상과 사진 한 장을 입력받습니다. 인터레이스가 있는 영상은 먼저 줄무늬를 정리하고, 해상도와 프레임 속도를 맞춥니다.” |
| 35-50s | Click the target face, drop the separate photo, correct its crop if needed, and show the generated gray canvas. | “영상 속 얼굴을 클릭하고 사진을 넣으면, 같은 위치에 사진의 얼굴을 배치한 참조 캔버스가 만들어집니다. 자동 선택이 맞지 않으면 직접 고칠 수 있습니다.” |
| 50-70s | Show the shared three-way player and the actual exported side-by-side video. Scrub to one selected frame, then play through a chunk join. | “원본, 사진 없는 복원, 사진을 넣은 복원을 같은 시점에서 봅니다. 두 복원은 같은 seed를 쓰고, 각각 자신의 이전 구간을 이어받습니다.” |
| 70-88s | Switch to the actual wipe MP4. Show a good region and a visible failure/limitation if present. Do not swap in a result from another seed. | “와이프를 움직이면 사진이 바꾼 부분을 더 쉽게 볼 수 있습니다. [실제 관찰 한 문장]. 움직임이 크거나 가려진 얼굴, 구간 경계에서는 여전히 오류가 생길 수 있습니다.” |
| 88-103s | Show the actual three-clip table: correct-minus-no-photo, correct-minus-wrong, common coverage. If evaluation is incomplete, show “Identity benefit: not yet established” instead of an empty success chart. | If measured: “고화질 정답 영상과 비교하고, 다른 사람 사진도 대조군으로 넣었습니다. 이 세 클립의 결과는 [실제 수치와 실패 포함].” If incomplete: “사진이 항상 더 정확한 얼굴을 만든다는 주장은 아직 검증되지 않았습니다.” |
| 103-113s | Briefly show local architecture and actual model names. Keep LTX Restore central. | “복원은 LTX-2.5와 Restore IC-LoRA로 실행합니다. 앱은 Comfy SDK와 로컬 proxy를 통해 제 PC의 ComfyUI에 연결합니다. 비공개 생성 API나 partner node는 쓰지 않습니다.” |
| 113-120s | End card: FaceTrue Restore, actual repo URL when public, setup instructions, one-person / short-clip / fixed-framing scope. | “한 사람, 짧은 영상, 고정된 구도부터 시작합니다. 생성된 세부를 정답으로 단정하지 않고, 사진의 효과를 비교할 수 있게 만들었습니다.” |

The opening narration describes the two conditions and does not claim a successful identity improvement. If the real result is not better, keep that fact visible. Do not call the method the first reference-based restoration system, or claim that similarity proves the original appearance was recovered.

## Result slots to fill from retained evidence

| Slot | Source | Current state |
|---|---|---|
| Opening result pair | Same paired run's no-photo/with-photo videos and manifest | Real result required |
| Independent photo provenance | Source/permission record | Required for selected assets |
| Runtime and memory, if displayed | Actual GPU preflight logs, with measurement method | Not measured |
| Three-clip identity table | Evaluation `summary.csv` + `frames.csv` + `run.json` | Not measured |
| Failure example | Actual frame/time from the selected run | Select after inspection |
| Public repo and demo URL | Owner-approved public repository and uploaded recording | Not published by this script |

If a slot remains unmeasured, omit the numerical claim or state “not measured.” The narration should not imply that a job runs in the edited playback time. If generation is sped up or skipped, label the time compression.

## Screen recording

1. Rehearse the UI in mock mode, with its notice visible. Do not reuse mock result clips in the final evidence sections.
2. Run the actual paired job in `FACETRUE_MODE=comfy`, save its complete outputs, and inspect the first/last frame and all joins before recording.
3. On the Mac, use the screen-recording controls (`Shift-Command-5`) to capture the app. Keep the separate photo and comparison readable. Close unrelated windows containing private information.
4. Insert the actual frame-aligned comparison exports into the recording. Preserve identical frame positions, label order and aspect ratio. Add the real reference photo as a separate panel for the opening.
5. Keep the same footage/source settings visible for both conditions. Include a failure or uncertainty rather than cropping every defect out of the demonstration.
6. Check the final duration and visible notices. A simple duration check is:

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 data/demo/final-demo.mp4
```

Use an actual exported file at that path. Keep the final duration below 120 seconds and retain the source run artifacts separately.

## Public-domain archival candidate

The inspected [Prelinger home-movie file on Wikimedia](https://commons.wikimedia.org/wiki/File:Home_Movies_-_Western_U.S.,_New_Mexico,_Mexico,_California,_Colorado,_Utah.webm) has a file-specific public-domain dedication record. [samples/README.md](../samples/README.md) records the source and the limits of that verification.

No matching independent portrait has been established for that film. It can become a separately labeled qualitative archival example after selecting a suitable shot and checking the source record. It cannot supply the claimed correct-person reference for the opening just because both images look old. Do not assume all Prelinger entries share the same rights.

## Submission preparation

The [official challenge page](https://comfy.org/open-source-higgsfield/) states October 30, 2026 at 09:00 PT: **October 31 at 01:00 KST**. The project's internal target is **October 30 at 22:00 KST**. Open Weights Only excludes partner nodes and closed APIs; the LTX VFX bonus requires LTX as the core video model.

Prepare, then let the repository owner perform the visibility change and submission:

- Public repository with the app license, installation instructions, upstream notices and actual limitations.
- A demo no longer than two minutes, with a verified URL.
- A model list copied from [MODELS.md](MODELS.md), including the local text encoder and optional evaluation models if used in the presented results.
- A `#OpenSourceHiggsfield` social post describing only demonstrated behavior.
- The submission form fields and URLs.

This plan does not publish a post, upload private material, submit the form, or change repository visibility. The owner controls those final actions.
