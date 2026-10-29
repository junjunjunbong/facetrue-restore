"""Run GFPGAN v1.4 / CodeFormer on FFHQ-aligned 512 faces (pure PyTorch via spandrel, no compile).
usage: fr_run.py in_dir out_dir"""
import sys, glob, os, numpy as np, torch
from PIL import Image
sys.path.insert(0, os.path.expanduser("~/facetrue-extra/fr/pylib"))
import spandrel, spandrel_extra_arches
spandrel_extra_arches.install()
W = os.path.expanduser("~/facetrue-extra/fr/w")
ind, outd = sys.argv[1], sys.argv[2]; os.makedirs(outd, exist_ok=True)
files = sorted(glob.glob(f"{ind}/*.png"))
for tag, wfile, opts in (("gfpgan", "GFPGANv1.4.pth", [None]), ("cf", "codeformer.pth", [0.5, 0.7])):
    m = spandrel.ModelLoader().load_from_file(f"{W}/{wfile}"); print(tag, m.architecture.name, flush=True)
    m = m.cuda().eval()
    for f in files:
        img = np.asarray(Image.open(f).convert('RGB')).astype(np.float32) / 255.0
        x = torch.from_numpy(img.copy()).permute(2, 0, 1)[None].cuda() * 2 - 1  # models expect [-1, 1]
        for w in opts:
            with torch.no_grad():
                torch.manual_seed(0)
                y = m.model(x, return_rgb=False) if w is None else m.model(x, weight=w)
            if isinstance(y, (tuple, list)): y = y[0]
            y = ((y + 1) / 2).clamp(0, 1)
            y = (y[0].permute(1, 2, 0).float().cpu().numpy() * 255).round().astype(np.uint8)
            name = os.path.basename(f)[:-4] + f"__{tag}" + ("" if w is None else f"{w}") + ".png"
            Image.fromarray(y).save(f"{outd}/{name}")
    del m; torch.cuda.empty_cache()
print("peak MiB", torch.cuda.max_memory_allocated() // 2**20)
