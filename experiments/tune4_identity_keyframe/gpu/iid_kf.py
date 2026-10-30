"""tune4 B2 (DIAGNOSTIC, license-conflicted): InstantID img2img (InstantX/InstantID, Apache-2.0) on RealVisXL V4.0, with the
face embedding from insightface antelopev2 glintr100.onnx (NON-COMMERCIAL research-only weights), run via onnxruntime
(no insightface package). Inputs/outputs as ipa_kf.py; kps = FFHQ template (inputs are FFHQ-aligned)."""
import sys, itertools, time
from pathlib import Path
import numpy as np, cv2, torch, onnxruntime as ort
from PIL import Image
from diffusers.models import ControlNetModel
from diffusers import DPMSolverMultistepScheduler
sys.path.insert(0, str(Path(__file__).parent))
from pipeline_stable_diffusion_xl_instantid_img2img import StableDiffusionXLInstantIDImg2ImgPipeline, draw_kps
D = Path(__file__).parent; IN = D / "in"; OUT = D / "out"; OUT.mkdir(exist_ok=True)
FFHQ = np.array([[192.98138, 239.94708], [318.90277, 240.1936], [256.63416, 314.01935], [201.26117, 371.41043], [313.08905, 371.15118]], np.float32)
ARC = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]], np.float32)
sess = ort.InferenceSession(str(D / "w/antelope/antelopev2/glintr100.onnx"), providers=["CPUExecutionProvider"])
M112, _ = cv2.estimateAffinePartial2D(FFHQ, ARC, method=cv2.LMEDS)
def embed(p512_bgr):
    a = cv2.warpAffine(p512_bgr, M112, (112, 112), flags=cv2.INTER_AREA)
    x = ((cv2.cvtColor(a, cv2.COLOR_BGR2RGB).astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None]
    return sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
cn = ControlNetModel.from_pretrained(str(D / "w/instantid/ControlNetModel"), torch_dtype=torch.float16)
pipe = StableDiffusionXLInstantIDImg2ImgPipeline.from_pretrained(str(D / "w/realvis"), controlnet=cn, variant="fp16", torch_dtype=torch.float16)
pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True)
pipe.to("cuda"); pipe.load_ip_adapter_instantid(str(D / "w/instantid/ip-adapter.bin")); pipe.set_progress_bar_config(disable=True)
kps_img = draw_kps(Image.new("RGB", (1024, 1024)), FFHQ * 2)
G = {"pd-obama": "man", "pd-biden": "elderly man", "pd-michelle": "woman"}
ips = [float(x) for x in sys.argv[1].split(",")]; strengths = [float(x) for x in sys.argv[2].split(",")]; srcs = sys.argv[3].split(",")
cns = float(sys.argv[4]) if len(sys.argv) > 4 else 0.8
t0 = time.time(); n = 0
for seed, clip, src, cond, sc, st in itertools.product((42, 7), G, srcs, ("correct", "wrong"), ips, strengths):
    name = f"s{seed}_{clip}_{src}__iid{sc}c{cns}_{st}_{cond}.png"
    if (OUT / name).exists(): continue
    f = IN / (f"s{seed}_{clip}_ltxarm_{cond}.png" if src == "ltxarm" else f"s{seed}_{clip}_{src}.png")
    init = Image.open(f).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    e = embed(cv2.imread(str(IN / f"{clip}_photo_{cond}.png")))
    pipe.set_ip_adapter_scale(sc)
    img = pipe(prompt=f"high quality photo of a {G[clip]}, detailed face, sharp focus, natural skin texture",
               negative_prompt="blurry, low quality, cartoon, painting, deformed, compression artifacts",
               image=init, control_image=kps_img, image_embeds=e, strength=st, controlnet_conditioning_scale=cns,
               num_inference_steps=30, guidance_scale=5.0, generator=torch.Generator("cuda").manual_seed(0)).images[0]
    img.resize((512, 512), Image.LANCZOS).save(OUT / name); n += 1
print("done", n, round(time.time() - t0, 1), "s; peak GB", round(torch.cuda.max_memory_allocated() / 1e9, 1), flush=True)
