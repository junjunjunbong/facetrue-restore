"""tune4 prep (Mac): FFHQ-aligned 512 crops of the correct/wrong reference photos per clip, plus tune3's aligned
frame-0 inputs (deg, ltx) and M. Output fr/in/."""
import sys, json, shutil
from pathlib import Path
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tune2"))
import ridkf as R
from app.evaluation import _photo
EVAL = R.EVAL; T = EVAL / "tune4"
man = json.loads((EVAL / "pilot-97.json").read_text())
for c in man["clips"]:
    for cond, key in (("correct", "reference"), ("wrong", "wrong_reference")):
        ph = _photo(EVAL / c[key]); k, _ = R.land(ph); a, _ = R.align(ph, k)
        cv2.imwrite(str(T / "fr" / "in" / f"{c['id']}_photo_{cond}.png"), a)
for f in (EVAL / "tune3" / "fr" / "in").iterdir():
    shutil.copy(f, T / "fr" / "in" / f.name)
print("ok")
# arm's own LTX frame 0 (photo-guided baseline), aligned with the no-photo M -> s<seed>_<clip>_ltxarm_<cond>.png
import numpy as np
for seed, b in {42: "run-97-strong", 7: "tune/runs/base_s7"}.items():
    for cid in ("pd-obama", "pd-biden", "pd-michelle"):
        M = np.load(T / "fr" / "in" / f"s{seed}_{cid}_M.npy")
        for cond in ("correct", "wrong"):
            fr = R.first(EVAL / b / cid / f"{cond}_reference.mp4")
            cv2.imwrite(str(T / "fr" / "in" / f"s{seed}_{cid}_ltxarm_{cond}.png"), cv2.warpAffine(fr, M, (512, 512), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT))
print("ok2")
