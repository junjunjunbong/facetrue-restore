"""tune4 B: LAB-match each IP-Adapter face (fr/out/s<seed>_<clip>_<src>__<gen>_<cond>.png) to the no-photo LTX frame-0
face, paste it on the seed's no-photo LTX frame 0 -> kf/<gen>_<src>_s<seed>/<clip>/<cond>_reference.png, and score the
keyframe alone vs GT frame 0 (SFace). Pre-gate: mean(correct) > 0.726 (no-photo frame 0) and correct > wrong."""
import sys, json
from pathlib import Path
from collections import defaultdict
import numpy as np, cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tune2"))
import ridkf as R
import app.evaluation as ev
EVAL = R.EVAL; T = EVAL / "tune4"
BASES = {42: "run-97-strong", 7: "tune/runs/base_s7"}
eng = ev.SFaceEngine(R.ROOT / "models" / "evaluation"); emb = lambda i: eng.observe(i).embedding
m = np.zeros((512, 512), np.uint8); cv2.ellipse(m, (256, 290), (170, 215), 0, 0, 360, 1, -1); sel = m > 0
def lab_match(a, b):
    a = cv2.cvtColor(a, cv2.COLOR_BGR2LAB).astype(np.float32); b = cv2.cvtColor(b, cv2.COLOR_BGR2LAB).astype(np.float32)
    for ch in range(3):
        a[..., ch] = (a[..., ch] - a[..., ch][sel].mean()) / (a[..., ch][sel].std() + 1e-6) * b[..., ch][sel].std() + b[..., ch][sel].mean()
    return cv2.cvtColor(np.clip(a, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
res = defaultdict(dict)
for seed, b in BASES.items():
    for cid in ("pd-obama", "pd-biden", "pd-michelle"):
        base = R.first(EVAL / b / cid / "without_reference.mp4"); gt = emb(R.first(EVAL / b / cid / "clean.mp4"))
        M = np.load(T / "fr" / "in" / f"s{seed}_{cid}_M.npy"); ltx = cv2.imread(str(T / "fr" / "in" / f"s{seed}_{cid}_ltx.png"))
        for f in sorted((T / "fr" / "out").glob(f"s{seed}_{cid}_*__*.png")):
            left, right = f.stem.split("__"); src = left[len(f"s{seed}_{cid}_"):]; gen, cond = right.rsplit("_", 1)
            face = lab_match(cv2.imread(str(f)), ltx)
            comp = R.paste(base.astype(np.float32), face.astype(np.float32), M)
            o = T / "kf" / f"{gen}_{src}_s{seed}" / cid; o.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(o / f"{cond}_reference.png"), comp)
            e = emb(comp)
            res[f"{gen}_{src}"][(seed, cid, cond)] = round(ev.cosine(e, gt), 3) if e is not None else None
json.dump({k: {f"{s}|{c}|{d}": x for (s, c, d), x in v.items()} for k, v in res.items()}, open(T / "kfscores4.json", "w"), indent=1)
print("| keyframe (correct/wrong) | s42 obama | s42 biden | s42 michelle | s7 obama | s7 biden | s7 michelle | mean corr | mean wrong | gate |")
print("|---" * 10 + "|")
rows = []
for v, d in res.items():
    cells, cs, ws, sep = [], [], [], True
    for s in (42, 7):
        for c in ("pd-obama", "pd-biden", "pd-michelle"):
            x, y = d.get((s, c, "correct")), d.get((s, c, "wrong")); cells.append(f"{x}/{y}")
            if x is None or y is None: sep = False; continue
            cs.append(x); ws.append(y); sep &= x > y
    mc = sum(cs) / max(len(cs), 1); mw = sum(ws) / max(len(ws), 1)
    rows.append((mc, f"| {v} | " + " | ".join(cells) + f" | {mc:.3f} | {mw:.3f} | {'PASS' if mc > 0.726 and sep and len(cs) == 6 else 'fail'} |"))
for _, r in sorted(rows, reverse=True): print(r)
