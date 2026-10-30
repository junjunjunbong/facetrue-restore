"""tune4 B: photo-conditioned frame-0 face via SDXL (RealVisXL V4.0) img2img + IP-Adapter plus-face (CLIP ViT-H, no insightface).
in/: s<seed>_<clip>_{ltx,ltxarm_<cond>}.png (FFHQ-aligned 512 frame-0 face), <clip>_photo_<cond>.png. out/: 512 faces."""
import sys, glob, os, itertools, time
from pathlib import Path
import torch
from PIL import Image
from diffusers import StableDiffusionXLImg2ImgPipeline, DPMSolverMultistepScheduler
from transformers import CLIPVisionModelWithProjection, CLIPImageProcessor
D = Path(__file__).parent; IN = D / "in"; OUT = D / "out"; OUT.mkdir(exist_ok=True)
enc_dir = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--laion--CLIP-ViT-H-14-laion2B-s32B-b79K/snapshots/*"))[0]
enc = CLIPVisionModelWithProjection.from_pretrained(enc_dir, torch_dtype=torch.float16)
pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(str(D / "w/realvis"), variant="fp16", torch_dtype=torch.float16,
                                                        image_encoder=enc, feature_extractor=CLIPImageProcessor())
pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True)
pipe.load_ip_adapter(str(D / "w/ipa"), subfolder="sdxl_models", weight_name="ip-adapter-plus-face_sdxl_vit-h.safetensors", image_encoder_folder=None)
pipe.to("cuda"); pipe.set_progress_bar_config(disable=True)
G = {"pd-obama": "man", "pd-biden": "elderly man", "pd-michelle": "woman"}
scales = [float(x) for x in sys.argv[1].split(",")]; strengths = [float(x) for x in sys.argv[2].split(",")]
srcs = sys.argv[3].split(","); seeds = [42, 7]
t0 = time.time(); n = 0
for seed, clip, src, cond, sc, st in itertools.product(seeds, G, srcs, ("correct", "wrong"), scales, strengths):
    name = f"s{seed}_{clip}_{src}__ipa{sc}_{st}_{cond}.png"
    if (OUT / name).exists(): continue
    f = IN / (f"s{seed}_{clip}_ltxarm_{cond}.png" if src == "ltxarm" else f"s{seed}_{clip}_{src}.png")
    init = Image.open(f).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    photo = Image.open(IN / f"{clip}_photo_{cond}.png").convert("RGB")
    pipe.set_ip_adapter_scale(sc)
    img = pipe(prompt=f"high quality photo of a {G[clip]}, detailed face, sharp focus, natural skin texture",
               negative_prompt="blurry, low quality, cartoon, painting, deformed, compression artifacts",
               image=init, ip_adapter_image=photo, strength=st, num_inference_steps=30, guidance_scale=5.0,
               generator=torch.Generator("cuda").manual_seed(0)).images[0]
    img.resize((512, 512), Image.LANCZOS).save(OUT / name); n += 1
print("done", n, round(time.time() - t0, 1), "s; peak GB", round(torch.cuda.max_memory_allocated() / 1e9, 1), flush=True)
