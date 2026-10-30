"""B: Qwen-Image-Edit-2511 pose-matched frame-0 keyframes.
Image1 = degraded frame-0 face crop (768 px), Image2 = arm photo (none arm: no Image2).
Output is soft-composited onto frame 0 of the no-photo LTX restore -> kf/qwen/<clip>/<cond>.png"""
import json, sys, time, uuid, subprocess, urllib.request, cv2, numpy as np
from pathlib import Path
EVAL = Path(__file__).resolve().parents[1]; OUT = EVAL / "tune5" / "kf" / "qwen"
HOST = "http://100.67.177.10:8188"; BASE = EVAL / "run-97-strong"
PROMPT = ("Restore the facial detail in Image 1 using the identity in Image 2. Preserve the exact head pose, expression, "
          "mouth opening, gaze, lighting, and framing of Image 1. Do not beautify the face or change the hairstyle.")
PROMPT_NONE = ("Restore the facial detail in Image 1. Preserve the exact head pose, expression, mouth opening, gaze, "
               "lighting, and framing of Image 1. Do not beautify the face or change the hairstyle.")
CROP = 768; GROW = 1.9
man = json.loads((EVAL / sys.argv[1] if len(sys.argv) > 1 else EVAL / "m42_om.json").read_text())

def first(p):
    c = cv2.VideoCapture(str(p)); ok, f = c.read(); c.release(); return f
def box(b, H, W):
    s = int(max(b["width"], b["height"]) * GROW); cx, cy = b["x"] + b["width"] // 2, b["y"] + b["height"] // 2
    x0 = int(np.clip(cx - s // 2, 0, W - s)); y0 = int(np.clip(cy - s // 2, 0, H - s)); return x0, y0, s
def post(g):
    r = urllib.request.Request(HOST + "/prompt", json.dumps({"prompt": g, "client_id": str(uuid.uuid4())}).encode(), {"Content-Type": "application/json"})
    pid = json.loads(urllib.request.urlopen(r).read())["prompt_id"]
    while True:
        h = json.loads(urllib.request.urlopen(f"{HOST}/history/{pid}").read())
        if pid in h and h[pid].get("status", {}).get("completed") is not None or (pid in h and h[pid]["status"].get("status_str") == "error"):
            return h[pid]
        time.sleep(2)
def graph(img1, img2, prefix, seed=42):
    g = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2511_fp8mixed.safetensors", "weight_dtype": "default"}},
         "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
         "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
         "4": {"class_type": "LoadImage", "inputs": {"image": img1}},
         "5": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["4", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 1}},
         "8": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": PROMPT if img2 else PROMPT_NONE, "vae": ["3", 0], "image1": ["5", 0]}},
         "9": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["2", 0], "prompt": "", "vae": ["3", 0], "image1": ["5", 0]}},
         "10": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": ["8", 0], "reference_latents_method": "index_timestep_zero"}},
         "11": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": ["9", 0], "reference_latents_method": "index_timestep_zero"}},
         "12": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.1}},
         "13": {"class_type": "CFGNorm", "inputs": {"model": ["12", 0], "strength": 1.0}},
         "14": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
         "15": {"class_type": "KSampler", "inputs": {"model": ["13", 0], "positive": ["10", 0], "negative": ["11", 0], "latent_image": ["14", 0],
                "seed": seed, "steps": 40, "cfg": 4.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
         "16": {"class_type": "VAEDecode", "inputs": {"samples": ["15", 0], "vae": ["3", 0]}},
         "17": {"class_type": "SaveImage", "inputs": {"images": ["16", 0], "filename_prefix": prefix}}}
    if img2:
        g["6"] = {"class_type": "LoadImage", "inputs": {"image": img2}}
        g["7"] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["6", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 1}}
        for n in ("8", "9"): g[n]["inputs"]["image2"] = ["7", 0]
    return g
def up(local, name): subprocess.run(["scp", "-q", str(local), f"gpu5090:ComfyUI/input/{name}"], check=True)

for cl in man["clips"]:
    clip = cl["id"]; d = OUT / clip; d.mkdir(parents=True, exist_ok=True)
    deg = first(BASE / clip / "degraded.mp4"); base = first(BASE / clip / "without_reference.mp4")
    H, W = deg.shape[:2]; x0, y0, s = box(cl["face_bbox"], H, W)
    crop = cv2.resize(deg[y0:y0 + s, x0:x0 + s], (CROP, CROP), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(d / "crop_degraded.png"), crop); up(d / "crop_degraded.png", f"q5_{clip}_crop.png")
    for cond, ref in (("without_reference", None), ("correct_reference", cl["reference"]), ("wrong_reference", cl["wrong_reference"])):
        t = time.time(); img2 = None
        if ref:
            img2 = f"q5_{clip}_{cond}_photo.png"; up(EVAL / ref, img2)
        h = post(graph(f"q5_{clip}_crop.png", img2, f"q5/{clip}_{cond}"))
        o = [i for v in h["outputs"].values() for i in v.get("images", [])]
        assert o, h["status"]
        img = urllib.request.urlopen(f"{HOST}/view?filename={o[0]['filename']}&subfolder={o[0]['subfolder']}&type=output").read()
        q = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR); cv2.imwrite(str(d / f"{cond}_qwen.png"), q)
        q = cv2.resize(q, (s, s), interpolation=cv2.INTER_AREA)
        # soft elliptical composite of the edited face onto frame 0 of the no-photo restore
        m = np.zeros((s, s), np.float32); b = cl["face_bbox"]
        cx, cy = b["x"] + b["width"] / 2 - x0, b["y"] + b["height"] / 2 - y0
        cv2.ellipse(m, (int(cx), int(cy)), (int(b["width"] * 0.62), int(b["height"] * 0.62)), 0, 0, 360, 1.0, -1)
        m = cv2.GaussianBlur(m, (0, 0), b["width"] * 0.08)[..., None]
        comp = base.copy().astype(np.float32); reg = comp[y0:y0 + s, x0:x0 + s]
        comp[y0:y0 + s, x0:x0 + s] = reg * (1 - m) + q.astype(np.float32) * m
        cv2.imwrite(str(d / f"{cond}.png"), np.clip(comp, 0, 255).astype(np.uint8))
        print(clip, cond, round(time.time() - t, 1), "s", flush=True)
