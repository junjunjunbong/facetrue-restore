"""Reject-rule metrics. Mac side (cv2): motion-compensated temporal error on frames 80-96 (warp out[t-1] onto t
with Farneback flow from the CLEAN clip, mean |out[t]-warp| in the face box, 0-255) and 256px face crops of
frames 0,8..96. 5090 side (torch+lpips, lpips_np.py): face LPIPS(alex) vs clean.
usage: python3 qual.py <run_dir rel. to data/eval-pd> [manifest]  -> <run>/qual.json"""
import sys, json, subprocess, cv2, numpy as np
from pathlib import Path
EVAL = Path(__file__).resolve().parents[1]; R = EVAL / sys.argv[1]
man = json.loads((EVAL / (sys.argv[2] if len(sys.argv) > 2 else "m42_om.json")).read_text())
def frames(p):
    c = cv2.VideoCapture(str(p)); out = []
    while True:
        ok, f = c.read()
        if not ok: break
        out.append(f)
    return out
res = {}; crops = {}
for cl in man["clips"]:
    clip = cl["id"]; b = cl["face_bbox"]; g = 0.3
    X0, Y0 = max(0, int(b["x"] - b["width"] * g / 2)), max(0, int(b["y"] - b["height"] * g / 2))
    X1, Y1 = int(b["x"] + b["width"] * (1 + g / 2)), int(b["y"] + b["height"] * (1 + g / 2))
    clean = frames(R / clip / "clean.mp4"); flows = {}
    for k in range(81, 97):
        flows[k] = cv2.calcOpticalFlowFarneback(cv2.cvtColor(clean[k], cv2.COLOR_BGR2GRAY), cv2.cvtColor(clean[k - 1], cv2.COLOR_BGR2GRAY),
                                                None, 0.5, 4, 21, 3, 5, 1.1, 0)
    H, W = clean[0].shape[:2]; gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    res[clip] = {}
    for arm in ("clean", "without_reference", "correct_reference", "wrong_reference"):
        v = frames(R / clip / f"{arm}.mp4")
        if len(v) < 97: continue
        errs = [np.abs(v[k][Y0:Y1, X0:X1].astype(np.float32) - cv2.remap(v[k - 1], gx + flows[k][..., 0], gy + flows[k][..., 1], cv2.INTER_LINEAR)[Y0:Y1, X0:X1]).mean() for k in range(81, 97)]
        res[clip][arm] = {"terr": round(float(np.mean(errs)), 3)}
        crops[f"{clip}|{arm}"] = np.stack([cv2.cvtColor(cv2.resize(v[i][Y0:Y1, X0:X1], (256, 256), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB) for i in range(0, 97, 8)])
np.savez_compressed("/tmp/q5crops.npz", **crops)
subprocess.run(["scp", "-q", "/tmp/q5crops.npz", str(Path(__file__).with_name("lpips_np.py")), "gpu5090:q5/"], check=True)
lp = json.loads(subprocess.run(["ssh", "gpu5090", "cd ~/q5 && PYTHONPATH=~/lpdeps ~/ComfyUI/.venv/bin/python lpips_np.py q5crops.npz 2>/dev/null"],
                               capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
for k, val in lp.items():
    clip, arm = k.split("|"); res[clip][arm]["lpips"] = val
(R / "qual.json").write_text(json.dumps(res, indent=1)); print(json.dumps(res))
