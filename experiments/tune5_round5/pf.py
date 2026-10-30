import csv,sys
def rows(p):
    d={}
    for r in csv.DictReader(open(p)):
        d[(r["clip_id"],int(r["frame_index"]),r["condition"])]=float(r["gt_cosine"]) if r["gt_cosine"] else float('nan')
    return d
B=rows("run-97-strong/frames.csv"); N=rows(sys.argv[1]+"/frames.csv")
for clip in ["pd-obama","pd-michelle"]:
  for cond in ["without_reference","correct_reference","wrong_reference"]:
    fr=sorted(k[1] for k in N if k[0]==clip and k[2]==cond)
    print(clip,cond[:5],"new",[round(N[(clip,f,cond)],2) for f in fr]); print(" "*len(clip),cond[:5],"bas",[round(B.get((clip,f,cond),float('nan')),2) for f in fr])
