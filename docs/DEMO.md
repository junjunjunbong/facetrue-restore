# FaceTrue Restore: 2-minute demo script (v3)

The final video must be **120 s or less**. Draft v3 is **107.2 s**, 1920×1080, 24 fps, H.264, silent (all narration is on-screen text).

**No real people appear in the demo.** The challenge agreement asks for no real people's likenesses without permission, so every face in the video is a **fictional person generated locally with open-weights LTX-2.5 22B**. Each segment that shows a face carries the caption:

> Fictional person generated with open models. Not a real individual.

The public-domain clips of real people (see [Benchmark sources](#benchmark-sources-not-shown-in-the-demo)) are used only for the measurements in [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md). The demo shows their aggregate numbers as text only.

## What the demo may claim

### Fictional grandma clip (shown in the demo)

- **Material:** a wide shot of a fictional elderly woman (`grandmaW_A_s11`, text-to-video, LTX-2.5 22B distilled, no LoRA).
  - Reference photo: frame 72 of a **separate** image-to-video close-up (`grandmaW_B_s23`), seeded from frame 120 of the wide clip, outside the evaluated frames 0-96. It is not a frame of the evaluated clip.
  - Wrong photo (control): a different fictional person (`auntW`, frame 56).
- **Damage was synthetic:** downscale to 1/5, Gaussian blur σ1.0, bicubic upscale, saturation 0.25, contrast 0.8 / brightness 0.03 / gamma 1.1, chroma shift, temporal grain, H.264 CRF 36 (`data/eval-pd/strong/evaluate_strong.py`).
- **Measurement:** SFace cosine to the clean clip, 13 sampled frames, seeds 42 and 7. Source: `data/eval-pd/synth/run_W42/summary.csv` and `run_W7/summary.csv` (local, not committed).

| Seed | Without photo | Correct photo | Wrong photo | Correct − without | Correct − wrong |
|---|---|---|---|---|---|
| 42 | 0.583 | 0.687 | 0.478 | **+0.103** | **+0.209** |
| 7 | 0.560 | 0.647 | 0.383 | **+0.087** | **+0.264** |

- **Coverage caveat:** a face was detected in only **7 of 13** sampled frames common to all three runs. Scores are means over those 7 frames. Coverage is below the harness's 80% bar, so its status is **"inconclusive"**.
- **Other fictional people:** father and aunt showed no clear gain (father −0.029 / −0.038; aunt +0.000 / +0.042, with correct = wrong at seed 7). The demo says so on the results slide.

### Public-domain benchmark (text only in the demo)

From [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) §4: 3 public-domain subjects, 13 sampled frames each, strong synthetic damage. Mean correct − no photo was **+0.092 (seed 42)** and **+0.064 (seed 7)**, and the correct photo scored higher than no photo in 38 of 39 frames for each seed. With the repository's mild damage the effect was small and mixed.

### Wording

- **Use:** "In our small test, adding a separate photo helped the restored face stay closer to the person, most clearly when the damage was heavy."
- **Do not use:** "keeps the face true", "recovers the original face", "unlimited length", claims about what other products refuse, or "first" reference-based restoration (IP-FVR and RG-FVR already exist).

### Visible side effects (shown, not cropped)

- It is generative: background, colors and fine detail can change in both versions.
- A higher similarity score is not proof that the original face was recovered. The face can also drift toward the reference photo itself.
- Scope: one person, short clips, fixed framing.

## Shot list (draft v3, 107.2 s)

All text is on screen. There is no voiceover track yet; the VO column is optional narration for a later pass.

| Time | Segment | On screen | Optional VO |
|---|---|---|---|
| 0:00-0:12 | Hook | `FaceTrue_wipe_synthetic.mp4`: face-zoomed wipe, "Without photo" (left) vs "With photo" (right). Top line: "Same damaged clip, restored twice. The only difference: one photo." Fictional caption. | "Same damaged video, restored twice. Same model, same seed. The only difference: on the right, I gave it one photo of her." |
| 0:12-0:18 | Title | "FaceTrue Restore. Anchor an old-video restoration to one photo, then see exactly what that photo changed." Model line. | — |
| 0:18-0:28 | Problem | Damaged clip (looping) next to the separate reference photo, with the damage recipe and "not a frame from the clip". Fictional caption. | "A restoration model has to invent the missing detail. Without a reference, it guesses whose face it is." |
| 0:28-0:33 | Web UI | Landing page of the app before any footage is loaded (first 2.9 s of `FaceTrue_UI_1_upload.mp4`, then a freeze). Caption: "1 Prepare video · 2 Face and photo · 3 Restore and compare". | "You start in the local web app." |
| 0:33-0:43 | Photo → canvas | Three panels: click the face in frame 0 of the damaged clip → separate photo → gray reference canvas with the face at the clicked position (`correct_canvas.png`). Fictional caption. | "Click the face, add a photo. The app places that face on a gray canvas at the same spot and feeds it in as an IC-LoRA guide." |
| 0:43-0:51 | 3-way comparison | `FaceTrue_4panel_synthetic.mp4`: Damaged input / Without photo / With photo / Original, same seed. Fictional caption. | "Same input, same seed. Without the photo the face drifts to a different-looking woman. With it, her features stay closer." |
| 0:51-0:59 | Wrong-photo control | Damaged input / Correct photo / Wrong person's photo / Original, with the two reference faces under their panels. Fictional caption. | "And with someone else's photo, the face moves away from her. The photo really steers identity." |
| 0:59-1:17 | Results | Grandma table (seeds 42 and 7), the 7/13 coverage note and "inconclusive" status, "father and aunt showed no clear gain", then the public-domain benchmark box as text only. | "On this clip, the correct photo raised similarity by 0.10 and 0.09, and beat the wrong photo by 0.21 and 0.26. A face was found in only 7 of 13 frames, so this is a small, inconclusive test. On three public-domain clips, the mean gain was 0.092 and 0.064." |
| 1:17-1:27 | Limits | Freeze frame (frame 60) without vs with photo, plus three limits bullets. Fictional caption. | "It's generative. Details change, and a similarity score is not proof. That's why the app always shows the comparison." |
| 1:27-1:39 | How it works | Web app (browser, Mac) → FastAPI → comfy-sdk + local proxy → ComfyUI on the RTX 5090 PC → LTX-2.5 22B + Restore IC-LoRA. Bullets: reference canvas, two renders with the same seed, 97-frame windows with 17-frame overlap, 8 steps · 1280×736 · about 72 s per window. Badge: "Open weights only". | "LTX-2.5 22B with the Restore IC-LoRA, in ComfyUI on one RTX 5090. Open weights only: no closed APIs, no partner nodes." |
| 1:39-1:47 | End card | "FaceTrue Restore", github.com/junjunjunbong/facetrue-restore, "Models: LTX-2.5 22B (distilled) + LTX-2.5 Restore IC-LoRA · open weights", #OpenSourceHiggsfield, scope line, fictional-person note. | "FaceTrue Restore: see what one photo changes. #OpenSourceHiggsfield" |

### Notes

- **Render time:** the app's render records show about 72 s per 97-frame window (8 steps, 1280×736) on one RTX 5090.
- **Window chaining:** the grandma clips are a single 97-frame window. Do not present them as a chained clip.
- **Web UI footage:** the existing screen recordings (`FaceTrue_UI_*.mp4`) show a real public figure after the first 3 s, so v3 uses only the empty landing page. A re-recording of the face-click, photo-drop and 3-way player steps with the fictional grandma clip would make this segment stronger.
- **Builder:** `/workspace/facetrue-demo/v3build/build.py` on the agent box (fonts: Source Sans Pro). Inputs are the grandma run files in `data/eval-pd/synth/run_W42/syn-grandmaW/` and the two synthetic demo clips.

## To do before publishing

- [x] Remove all real-person footage and stills from the demo (v3).
- [ ] Optional: re-record the web UI steps with the fictional grandma clip.
- [ ] Optional: add a voiceover track (AAC) using the VO column.
- [ ] Use the repo URL on the end card only after the repository is public.
- [ ] Before recording anything new: close unrelated windows; no `.env`, tokens or private files visible.
- [ ] Final duration check (≤ 120 s):

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 FaceTrue_demo_2min_draft_v3.mp4
```

## Benchmark sources (not shown in the demo)

These public-domain US federal government works were used only for the measurements in the technical report. They do not appear in the demo video.

| Use | Source |
|---|---|
| Obama clip | [2013-09-28 President Obama's Weekly Address (HD)](https://commons.wikimedia.org/wiki/File:2013-09-28_President_Obama%27s_Weekly_Address_HD.webm), The White House, from 295.5 s |
| Obama reference | [President Barack Obama](https://commons.wikimedia.org/wiki/File:President_Barack_Obama.jpg), official portrait by Pete Souza, 2012 |
| Obama control photo | [Mike Pence official Vice Presidential portrait](https://commons.wikimedia.org/wiki/File:Mike_Pence_official_Vice_Presidential_portrait.jpg), D. Myles Cullen |
| Biden clip | [2016-07-09 VPOTUS Weekly Address (HD)](https://commons.wikimedia.org/wiki/File:20160709_VPOTUS_Weekly_Address_HD.webm), The White House, from 105.5 s |
| Biden reference | [Joe Biden official portrait 2013](https://commons.wikimedia.org/wiki/File:Joe_Biden_official_portrait_2013.jpg), David Lienemann |
| Biden control photo | [John Kerry official Secretary of State portrait](https://commons.wikimedia.org/wiki/File:John_Kerry_official_Secretary_of_State_portrait.jpg), US Department of State |
| Michelle Obama clip | [Weekly Address: The First Lady Marks Mother's Day…](https://commons.wikimedia.org/wiki/File:Weekly_Address-_The_First_Lady_Marks_Mother%27s_Day_and_Speaks_Out_on_the_Tragic_Kidnapping_in_Nigeria.webm), The White House, 2014-05-10, from 277.5 s |
| Michelle Obama reference | [Michelle Obama 2013 official portrait](https://commons.wikimedia.org/wiki/File:Michelle_Obama_2013_official_portrait.jpg), Chuck Kennedy |
| Michelle Obama control photo | [Kamala Harris Vice Presidential Portrait (cropped)](https://commons.wikimedia.org/wiki/File:Kamala_Harris_Vice_Presidential_Portrait_(cropped).jpg), Lawrence Jackson |

Models are listed in [MODELS.md](MODELS.md): LTX-2.x Community License for LTX-2.5, the Restore IC-LoRA and the Gemma 4 text encoder package. Evaluation-only models: YuNet (MIT) and SFace (Apache-2.0).

## Submission preparation

The [official challenge page](https://comfy.org/open-source-higgsfield/) gives the deadline as October 30, 2026 at 09:00 PT (**October 31 at 01:00 KST**). The internal target is **October 30 at 22:00 KST**. Open Weights Only excludes partner nodes and closed APIs. The LTX VFX bonus requires LTX as the core video model.

The project owner performs these steps personally. This document does not publish a post, upload media, submit the form or change repository visibility.

- Public repository with the app license, installation instructions, upstream notices and actual limitations.
- The demo video, no longer than two minutes, with a verified URL.
- The model list from [MODELS.md](MODELS.md).
- A `#OpenSourceHiggsfield` social post that describes only demonstrated behavior.
- The submission form fields and URLs.
