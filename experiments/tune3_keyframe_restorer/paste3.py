"""Paste restored 512 faces back on the seed's no-photo LTX frame 0 -> kf/<variant>_s<seed>/<clip>/<cond>.png
(same face for every arm: GFPGAN/CodeFormer take no reference photo). Scores the keyframe vs GT frame 0 (SFace)."""
import sys, json
from pathlib import Path
import numpy as np, cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tune2"))
import ridkf as R
import app.evaluation as ev
EVAL = R.EVAL; T = EVAL / "tune3"
BASES = {42: "run-97-strong", 7: "tune/runs/base_s7"}
eng = ev.SFaceEngine(R.ROOT / "models" / "evaluation"); emb = lambda i: eng.observe(i).embedding
res = []
for seed, b in BASES.items():
    for cid in ("pd-obama", "pd-biden", "pd-michelle"):
        base = R.first(EVAL / b / cid / "without_reference.mp4"); gt = emb(R.first(EVAL / b / cid / "clean.mp4"))
        M = np.load(T / "fr" / "in" / f"s{seed}_{cid}_M.npy")
        res.append(dict(seed=seed, clip=cid, variant="ltx_frame0(no kf)", gt=round(ev.cosine(emb(base), gt), 3)))
        for f in sorted((T / "fr" / "out").glob(f"s{seed}_{cid}_*.png")):
            left, gen = f.stem.split("__"); src = left.split("_")[-1]
            v = f"{gen}_{src}"
            comp = R.paste(base.astype(np.float32), cv2.imread(str(f)).astype(np.float32), M)
            o = T / "kf" / f"{v}_s{seed}" / cid; o.mkdir(parents=True, exist_ok=True)
            for cond in ("correct_reference", "wrong_reference", "without_reference"): cv2.imwrite(str(o / f"{cond}.png"), comp)
            e = emb(comp)
            res.append(dict(seed=seed, clip=cid, variant=v, gt=round(ev.cosine(e, gt), 3) if e is not None else None))
json.dump(res, open(T / "kfscores.json", "w"), indent=1)
from collections import defaultdict
t = defaultdict(dict)
for r in res: t[(r["variant"])][(r["seed"], r["clip"])] = r["gt"]
cols = [(s, c) for s in (42, 7) for c in ("pd-obama", "pd-biden", "pd-michelle")]
print("| keyframe | " + " | ".join(f"s{s} {c[3:]}" for s, c in cols) + " | mean |"); print("|---" * 8 + "|")
for v, d in t.items():
    vals = [d.get(k) for k in cols]; ok = [x for x in vals if x is not None]
    print(f"| {v} | " + " | ".join(str(x) for x in vals) + f" | {sum(ok)/len(ok):.3f} |")
