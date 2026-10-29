"""degc variants (as tune2 degbc): LAB mean/std transfer of the restored 512 face to the aligned no-photo LTX frame-0 face
(inside the paste ellipse), written as fr/out/<stem>c... then re-run paste3.py."""
import cv2, numpy as np
from pathlib import Path
O = Path(__file__).parent / "fr"
m = np.zeros((512, 512), np.uint8); cv2.ellipse(m, (256, 290), (170, 215), 0, 0, 360, 1, -1); sel = m > 0
for f in sorted((O / "out").glob("*_deg__*.png")):
    seed_clip = f.stem.split("_deg__")[0]; gen = f.stem.split("__")[1]
    a = cv2.cvtColor(cv2.imread(str(f)), cv2.COLOR_BGR2LAB).astype(np.float32)
    b = cv2.cvtColor(cv2.imread(str(O / "in" / f"{seed_clip}_ltx.png")), cv2.COLOR_BGR2LAB).astype(np.float32)
    for ch in range(3):
        a[..., ch] = (a[..., ch] - a[..., ch][sel].mean()) / (a[..., ch][sel].std() + 1e-6) * b[..., ch][sel].std() + b[..., ch][sel].mean()
    cv2.imwrite(str(O / "out" / f"{seed_clip}_degc__{gen}.png"), cv2.cvtColor(np.clip(a, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR))
print("ok")
