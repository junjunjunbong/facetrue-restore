# FaceTrue Restore: 2-minute demo script

The target is a final video of **115-118 s, with a hard limit of 120 s**. It is built around two finished comparison clips from a real GPU run, plus screen captures of the web UI that still need to be recorded (see [Shots still to record](#shots-still-to-record)).

## What the demo may claim

These are the only results we can stand behind. They come from a small pilot run: three clips, one seed (42), 97 frames each, with LTX-2.5 22B + Restore IC-LoRA (8 steps) on one RTX 5090.

- **Material:** public-domain White House weekly-address footage of Barack Obama, Joe Biden and Michelle Obama. A separate official portrait of each person was used as the reference photo, and a different person's portrait was used as a control.
- **Damage was synthetic.** The clean clips were degraded on purpose to look like old VHS. This is not recovered tape.
- **Damage recipe:** downscale to 1/5 size, Gaussian blur σ1.0, upscale with bicubic, reduce saturation to 0.25, lower the contrast, shift the chroma, add temporal grain, encode with H.264 CRF 36.
  - This recipe was applied by a local wrapper around `scripts/evaluate.py` and is not in the repository.
  - The repository default is milder.
- **Measurement:** SFace face-embedding cosine against the clean original, on 13 sampled frames per clip. A face was detected in every sampled frame of every condition.

| Clip | Damaged vs. original | No photo | Correct photo | Other person's photo | Correct − no photo | Correct − other photo | Frames where correct photo wins (vs. no photo / vs. other) |
|---|---|---|---|---|---|---|---|
| Obama | 0.680 | 0.728 | 0.861 | 0.694 | +0.133 | +0.167 | 13/13, 13/13 |
| Biden | 0.692 | 0.652 | 0.762 | 0.654 | +0.111 | +0.108 | 13/13, 13/13 |
| Michelle Obama | 0.608 | 0.773 | 0.804 | 0.783 | +0.031 | +0.020 | 12/13, 12/13 |

- **Mild damage gave small, mixed results.** We also ran the repository's default mild damage, where the damaged input was already about 0.87-0.89 similar to the original. There the photo's effect was small and mixed: at 240 frames, correct − no photo was +0.014 (Obama), +0.005 (Biden) and −0.003 (Michelle Obama).
- **Wording to use:** "In our small test, adding a real photo helped the restored face look more like the real person, most clearly when the damage was heavy."
- **Wording not to use:**
  - "keeps the face true"
  - "recovers the original face"
  - "unlimited length"
  - any claim about what other video products refuse to process
  - "first" reference-based restoration (IP-FVR and RG-FVR already exist)

### Visible side effects

Say these out loud in the demo instead of cropping them out:

- **The background can change.** In the Biden pair, the flag behind him is visible without the photo, but a plain dark wall appears with the photo. The reference canvas is a gray frame, and the model can also restyle areas outside the face.
- **The photo version can look stylized.** In the Biden pair, the with-photo face is sharper and more contrasty, and the eye color is more saturated than in the original.
- **A similarity score is not proof.** It is not proof that the original appearance was recovered. The restored face can also drift toward the reference photo itself.

## Finished clips

These are local files and are not committed. They were generated from `data/eval-pd/run-97-strong/pd-biden/` by `data/eval-pd/demo/make_demo.py`.

| Clip | File | Length | Content |
|---|---|---|---|
| Wipe | `data/eval-pd/demo/biden_wipe.mp4` | 12.1 s (97 frames × 3 loops), 1920×1080, 24 fps | Face-zoomed. Left "Without photo", right "With real photo". A divider sweeps across. Caption: "Same damaged VHS-style input · same seed · only the reference photo differs". |
| 4-panel | `data/eval-pd/demo/biden_4panel.mp4` | 8.1 s (97 frames × 2 loops), 1920×1080, 24 fps | Damaged input / Without photo / With real photo / Original. **The burned-in title still reads "one reference photo keeps the face true".** Re-render it with the toned-down title before using it (see checklist). |

The video loops back at 4.04 s and 8.08 s, which causes a small jump. Cut on the loop point or play only one pass when time is short.

## Shot list (118 s)

VO = voiceover. On-screen text is in quotes. Times are cumulative.

| Time | On screen | VO / caption (English) |
|---|---|---|
| **0:00-0:12** Hook | **Wipe clip** at full screen, first pass, with the divider sweeping. Small corner caption: "Synthetic VHS-style damage · public-domain footage". | "Same damaged video, restored twice on my own PC. Same model, same seed. The only difference: on the right, I gave it one real photo of the person." |
| **0:12-0:24** Problem | **4-panel clip** (re-rendered title): damaged / without photo / with real photo / original. Hold on it once it reaches the "Original" panel. | "Old tape loses the face. A restoration model fills in the missing detail, but it has to guess whose face it is. FaceTrue Restore lets you hand it a separate photo, and shows you exactly what that photo changed." |
| **0:24-0:36** Upload | Web UI screen capture: upload the clip, tick "synthetic test clip", show the first frame. | "You start with a short clip of one person. The app can deinterlace it and normalizes size and frame rate." |
| **0:36-0:50** Face + photo | Click the face in the first frame. Drop the separate portrait. Show the crop preview, then the gray reference canvas with the face placed at the clicked position. | "Click the face, drop in a separate photo, not a frame from the video. The app places that face on a reference canvas, at the same spot as the face in the video." |
| **0:50-1:04** Run + 3-way player | Start the job (sped up, with an on-screen "sped up" label). Then the synchronized player: original / without photo / with photo. Scrub, and pause on one frame. | "It renders the clip twice, with and without the photo, using the same seed. All three views stay on the same frame, so you can compare them directly." Caption: "Sped up. Real render: about a minute per 97-frame pass on one RTX 5090." |
| **1:04-1:24** Results | Results table card with the three clips and the correct − no photo / correct − other photo columns (numbers from the table above). Note under the card: "3 clips · 1 seed · synthetic damage". | "We tested it on three public-domain clips with heavy synthetic damage, against a no-photo run and a wrong-person photo. With the right photo, the face matched the real person more closely in all three, clearly for two of them and only slightly for the third. With mild damage, the effect was small. This is a small test, not a benchmark." |
| **1:24-1:34** Honest limits | Pause the wipe on a frame where the background differs (the flag vs. the dark wall). | "It's generative. The background and color can change too, and similarity is not proof the original was recovered. That's why the app always shows the comparison." |
| **1:34-1:50** How it works | Simple diagram: Mac (web app + FastAPI) → comfy-sdk → local proxy → ComfyUI on the RTX 5090 PC → LTX-2.5 22B + Restore IC-LoRA. Then: reference canvas, plus 97-frame windows with 17-frame overlap. Badge: "Open weights only". | "Under the hood: LTX-2.5 22B with the Restore IC-LoRA, running in ComfyUI on a single RTX 5090. The photo enters as a reference canvas. Longer clips are restored in 97-frame windows with a 17-frame overlap. Open weights only: no closed APIs, no partner nodes." |
| **1:50-1:58** End card | "FaceTrue Restore". github.com/junjunjunbong/facetrue-restore. #OpenSourceHiggsfield. "One person · short clips · fixed framing". | "FaceTrue Restore: see what one photo changes. Link below. #OpenSourceHiggsfield" |

### Notes on timing and wording

- **Render time:** in the strong-damage pilot, 9 renders of 97 frames took 662 s in total, about 74 s each including loading. Peak GPU memory was about 31.9 GB, from `nvidia-smi` sampling for the whole GPU, with ComfyUI running in `--lowvram`. Use "about a minute per 97-frame pass", or leave the number out.
- **Window chaining:** the finished Biden clips are a single 97-frame window. The separate 240-frame (10 s) pilot ran through the 97/17 window chaining. Do not show a chained clip as if it were the Biden demo.
- **If a family-video example is added:** it must be public domain, or 준원's own footage used with the consent of everyone shown. Do not use private family media without consent. Do not upload private media to outside services.

## Shots still to record

Checklist for 준원:

- [ ] **Re-render the 4-panel clip** with a toned-down title, for example "FaceTrue Restore: does one real photo help?", or with no title. The current file says "keeps the face true".
- [ ] **Web UI, upload (0:24-0:36):** upload `biden-hq`-derived degraded input or another public-domain clip. Tick the synthetic-test checkbox, and keep the "SYNTHETICALLY DEGRADED TEST CLIP" label visible.
- [ ] **Web UI, face click and photo drop (0:36-0:50):** click the face, drop `biden-photo.jpg`, show the crop preview and the gray reference canvas.
- [ ] **Web UI, run and 3-way player (0:50-1:04):** a real `FACETRUE_MODE=comfy` run, not mock output. Sped-up footage needs a "sped up" label. Scrub the synchronized player and pause on one frame.
- [ ] **Results card (1:04-1:24):** a simple slide built from the table above, including the "3 clips · 1 seed · synthetic damage" note.
- [ ] **Limits freeze frame (1:24-1:34):** a wipe frame where the background difference is visible.
- [ ] **How-it-works diagram (1:34-1:50):** a static slide.
- [ ] **End card (1:50-1:58):** use the repo URL only after the repository is public.
- [ ] **Before recording:** close unrelated windows, and check that no `.env`, tokens or private files are visible.
- [ ] **Final duration check:** keep the export at 120 s or less. Check it with:

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 data/demo/final-demo.mp4
```

Mock mode is fine for rehearsal, but its outputs are copies of the input and must not appear in the final video as restorations.

## Sources and licenses

All footage and photos in the demo are US federal government works in the **public domain**, taken from Wikimedia Commons. These sources are recorded in `data/eval-pd/pilot-97.json`, which is local and not committed. Each clip was trimmed to 11 s and normalized to 1280×736 at 24 fps.

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

**Rights and endorsement:**

- The people shown are public figures, and the footage is used only to demonstrate restoration. The demo must not suggest that they endorse the project.
- Public-domain status covers copyright only. Check each Commons file page again before publishing.
- Models are listed in [MODELS.md](MODELS.md): LTX-2.x Community License for LTX-2.5, the Restore IC-LoRA and the Gemma 4 text encoder package. The evaluation-only models are YuNet (MIT) and SFace (Apache-2.0).

The [Prelinger home-movie file](https://commons.wikimedia.org/wiki/File:Home_Movies_-_Western_U.S.,_New_Mexico,_Mexico,_California,_Colorado,_Utah.webm) remains a possible archival extra (see [samples/README.md](../samples/README.md)). There is no independent photo of the people in it, so it can only serve as a clearly labeled qualitative example, never as a correct-photo test.

## Submission preparation

The [official challenge page](https://comfy.org/open-source-higgsfield/) gives the deadline as October 30, 2026 at 09:00 PT, which is **October 31 at 01:00 KST**. The project's internal target is **October 30 at 22:00 KST**. Open Weights Only excludes partner nodes and closed APIs. The LTX VFX bonus requires LTX as the core video model.

The owner (준원) performs these steps personally. This document does not publish a post, upload media, submit the form or change repository visibility.

- Public repository with the app license, installation instructions, upstream notices and actual limitations.
- The demo video, no longer than two minutes, with a verified URL.
- The model list from [MODELS.md](MODELS.md).
- A `#OpenSourceHiggsfield` social post that describes only demonstrated behavior.
- The submission form fields and URLs.
