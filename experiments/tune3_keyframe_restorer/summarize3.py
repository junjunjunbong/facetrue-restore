import csv, json
from pathlib import Path
from collections import defaultdict
E = Path(__file__).resolve().parents[1]
runs = [("baseline", E / "run-97-strong"), ("base_s7", E / "tune/runs/base_s7")]
runs += [("kf_rid(tune2,s42)", E / "tune2/runs/kf_rid"), ("kf_oracle(tune2,s42)", E / "tune2/runs/kf_oracle")]
runs += [(p.name, p) for p in sorted((E / "tune3" / "runs").iterdir(), key=lambda p: p.name)] if (E / "tune3" / "runs").exists() else []
K = ("without_reference", "correct_reference", "wrong_reference")
out = ["| run | clip | none | correct | wrong | c-n | c-w | c>n frames | c>w frames | c-n excl. frame 0 | photo-cos correct (pasted-look check) | render s |", "|" + "---|" * 12]
for name, d in runs:
    if not (d / "frames.csv").exists(): continue
    f = defaultdict(dict); pc = defaultdict(dict)
    for r in csv.DictReader(open(d / "frames.csv")):
        if r["gt_cosine"]:
            f[(r["clip_id"], int(r["frame_index"]))][r["condition"]] = float(r["gt_cosine"])
            pc[(r["clip_id"], int(r["frame_index"]))][r["condition"]] = float(r["correct_photo_cosine"])
    rj = json.loads((d / "run.json").read_text()); times = rj.get("render_seconds", {})
    tot = defaultdict(list)
    for clip in ["pd-obama", "pd-biden", "pd-michelle"]:
        keys = [k for k in f if k[0] == clip and len(f[k]) == 3]
        if not keys: continue
        m = {c: sum(f[k][c] for k in keys) / len(keys) for c in K}
        k0 = [k for k in keys if k[1] != 0]
        ex = sum(f[k]["correct_reference"] - f[k]["without_reference"] for k in k0) / len(k0)
        p = sum(pc[k]["correct_reference"] for k in keys) / len(keys)
        won = sum(f[k]["correct_reference"] > f[k]["without_reference"] for k in keys)
        ww = sum(f[k]["correct_reference"] > f[k]["wrong_reference"] for k in keys)
        out.append(f"| {name} | {clip} | {m[K[0]]:.3f} | {m[K[1]]:.3f} | {m[K[2]]:.3f} | {m[K[1]]-m[K[0]]:+.3f} | {m[K[1]]-m[K[2]]:+.3f} | {won}/{len(keys)} | {ww}/{len(keys)} | {ex:+.3f} | {p:.3f} | {times.get(clip + '/correct_reference', '')} |")
        for c in K: tot[c].append(m[c])
        tot["ex"].append(ex); tot["p"].append(p); tot["won"].append(won); tot["n"].append(len(keys))
    if len(tot["n"]) == 3:
        a = {k: sum(v) / 3 for k, v in tot.items()}
        out.append(f"| **{name}** | MEAN | {a[K[0]]:.3f} | {a[K[1]]:.3f} | {a[K[2]]:.3f} | **{a[K[1]]-a[K[0]]:+.3f}** | {a[K[1]]-a[K[2]]:+.3f} | {sum(tot['won'])}/{sum(tot['n'])} |  | {a['ex']:+.3f} | {a['p']:.3f} | wall {rj.get('wall_seconds', '')} |")
print("\n".join(out))
