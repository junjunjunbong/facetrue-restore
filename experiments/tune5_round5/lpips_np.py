import sys, json, numpy as np, torch, lpips
d = np.load(sys.argv[1]); net = lpips.LPIPS(net="alex", verbose=False).cuda()
t = lambda a: torch.from_numpy(a).permute(0, 3, 1, 2).float().div(127.5).sub(1).cuda()
out = {}
with torch.no_grad():
    for k in d.files:
        clip, arm = k.split("|")
        if arm == "clean": continue
        out[k] = round(float(net(t(d[k]), t(d[f"{clip}|clean"])).mean()), 4)
print(json.dumps(out))
