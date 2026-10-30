import sys,json
from pathlib import Path
import numpy as np,cv2
ROOT=Path("../..").resolve(); sys.path.insert(0,str(ROOT))
import app.evaluation as ev
eng=ev.SFaceEngine(ROOT/"models/evaluation")
def e(img): return np.array(eng.observe(img).embedding)
def c(a,b): return round(float(a@b/np.linalg.norm(a)/np.linalg.norm(b)),3)
for clip in ["pd-obama","pd-michelle"]:
    cap=cv2.VideoCapture(f"run-97-strong/{clip}/clean.mp4"); _,cl=cap.read(); ec=e(cl)
    out={}
    for k in ["without_reference","correct_reference","wrong_reference"]:
        out[k]=c(ec,e(cv2.imread(f"tune5/kf/qwen/{clip}/{k}.png")))
    print(clip,"kf vs clean f0",out)
