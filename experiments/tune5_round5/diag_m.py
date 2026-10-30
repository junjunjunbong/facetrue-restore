import sys, json, csv
from pathlib import Path
import numpy as np, cv2
ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT))
import app.evaluation as ev
E=ROOT/"data/eval-pd"; eng=ev.SFaceEngine(ROOT/"models/evaluation")
man=json.load(open(E/"pilot-97.json"))
def frames(p):
    cap=cv2.VideoCapture(str(p)); out=[]
    while True:
        ok,f=cap.read()
        if not ok: break
        out.append(f)
    return out
def land(img):
    h,w=img.shape[:2]; s=min(1,640/max(w,h)); sm=cv2.resize(img,(round(w*s),round(h*s)))
    eng.detector.setInputSize((sm.shape[1],sm.shape[0])); _,f=eng.detector.detect(sm); f=f[0].copy(); f[:14]/=s; return f
def emb(img): return np.array(eng.observe(img).embedding)
def cos(a,b): return float(a@b/np.linalg.norm(a)/np.linalg.norm(b))
def rows(path):
    d={}
    for r in csv.DictReader(open(path)):
        d[(r["clip_id"],int(r["frame_index"]),r["condition"])]=float(r["gt_cosine"]) if r["gt_cosine"] else None
    return d
R={42:rows(E/"run-97-strong/frames.csv"),7:rows(E/"tune/runs/base_s7/frames.csv")}
res={}
for c in man["clips"]:
    cid=c["id"]; cl=frames(E/"run-97-strong"/cid/"clean.mp4"); idx=sorted(set(range(0,97,8))|{96})
    ref=emb(ev._photo(E/c["reference"])); wr=emb(ev._photo(E/c["wrong_reference"]))
    e={i:emb(cl[i]) for i in idx}
    ref_c=[cos(ref,e[i]) for i in idx]; wr_c=[cos(wr,e[i]) for i in idx]; f0=[cos(e[0],e[i]) for i in idx[1:]]
    pf=[]
    for i in idx:
        f=land(cl[i]); x,y,w,h=f[:4]; re,le,no,rm,lm=f[4:14].reshape(5,2)
        eyem=(re+le)/2; ed=np.linalg.norm(le-re); yaw=float((no[0]-eyem[0])/ed)
        mouthw=float(np.linalg.norm(lm-rm)/ed); nose_mouth=float((((rm+lm)/2)[1]-no[1])/ed)
        x0,y0=int(max(0,x)),int(max(0,y)); br=float(cv2.cvtColor(cl[i][y0:y0+int(h),x0:x0+int(w)],cv2.COLOR_BGR2GRAY).mean())
        d={s:(R[s][(cid,i,"correct_reference")]-R[s][(cid,i,"without_reference")]) for s in (42,7) if R[s].get((cid,i,"correct_reference")) is not None and R[s].get((cid,i,"without_reference")) is not None}
        pf.append(dict(f=i,yaw=round(yaw,3),mouthw=round(mouthw,3),nose_mouth=round(nose_mouth,3),bright=round(br,1),ref_cos=round(cos(ref,e[i]),3),cn42=round(d.get(42,np.nan),3),cn7=round(d.get(7,np.nan),3),none42=R[42].get((cid,i,"without_reference"))))
    fr=ev._photo(E/c["reference"]); fl=land(fr); re,le,no=fl[4:6],fl[6:8],fl[8:10]; ph_yaw=float((no[0]-(re[0]+le[0])/2)/np.linalg.norm(le-re))
    res[cid]=dict(ref_vs_clean_mean=round(np.mean(ref_c),3),ref_vs_clean_min=round(min(ref_c),3),ref_vs_clean_max=round(max(ref_c),3),
      wrong_vs_clean_mean=round(np.mean(wr_c),3),clean_f0_vs_others_mean=round(np.mean(f0),3),clean_f0_vs_others_min=round(min(f0),3),photo_yaw=round(ph_yaw,3),
      corr_yaw_cn42=round(float(np.corrcoef([p["yaw"] for p in pf],[p["cn42"] for p in pf])[0,1]),2),
      corr_abs_yaw_cn42=round(float(np.corrcoef([abs(p["yaw"]) for p in pf],[p["cn42"] for p in pf])[0,1]),2),
      corr_mouth_cn42=round(float(np.corrcoef([p["nose_mouth"] for p in pf],[p["cn42"] for p in pf])[0,1]),2),
      corr_bright_cn42=round(float(np.corrcoef([p["bright"] for p in pf],[p["cn42"] for p in pf])[0,1]),2),
      corr_refcos_cn42=round(float(np.corrcoef([p["ref_cos"] for p in pf],[p["cn42"] for p in pf])[0,1]),2),
      corr_none_cn42=round(float(np.corrcoef([p["none42"] for p in pf],[p["cn42"] for p in pf])[0,1]),2),
      frames=pf)
json.dump(res,open(E/"tune5/diag/michelle_diag.json","w"),indent=1)
for k,v in res.items():
    print(k,{a:b for a,b in v.items() if a!="frames"})
for p in res["pd-michelle"]["frames"]: print(p)
