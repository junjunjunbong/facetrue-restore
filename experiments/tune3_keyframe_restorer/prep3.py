"""tune3 prep (Mac): FFHQ-align frame 0 of the degraded clip (and of the no-photo LTX restore) to 512 per seed,
using landmarks from the seed's no-photo LTX frame 0 (same as tune2/ridprep.py). Writes fr/in/s<seed>_<clip>_{deg,ltx}.png + M."""
import sys, json
from pathlib import Path
import numpy as np, cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tune2"))
import ridkf as R
EVAL = R.EVAL; T = EVAL / "tune3"
BASES = {42: "run-97-strong", 7: "tune/runs/base_s7"}
for seed, b in BASES.items():
    for cid in ("pd-obama", "pd-biden", "pd-michelle"):
        ltx = R.first(EVAL / b / cid / "without_reference.mp4"); deg = R.first(EVAL / b / cid / "degraded.mp4")
        kps, _ = R.land(ltx)
        for name, img in (("deg", deg), ("ltx", ltx)):
            a, M = R.align(img, kps); cv2.imwrite(str(T / "fr" / "in" / f"s{seed}_{cid}_{name}.png"), a)
        np.save(T / "fr" / "in" / f"s{seed}_{cid}_M.npy", M)
print("ok")
