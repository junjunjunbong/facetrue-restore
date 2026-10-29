#!/usr/bin/env python3
"""Local, gitignored tuning sweep. Same strong-VHS degradation + SFace scoring as
strong/evaluate_strong.py; applies graph/canvas overrides from a JSON config.
Usage: sweep.py <config.json>   (config: name, seed, lora, vid_strength, ref_strength,
ref_frame_idx, ref_extra_idx[list], steps, expand, color_match, reuse_without)"""
import asyncio, json, math, shutil, sys, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
EVAL = ROOT / "data" / "eval-pd"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(EVAL / "strong"))
import app.evaluation as ev
import app.workflow as wf
import app.comfy_backend as cb
from recipe import vf

C = json.loads(Path(sys.argv[1]).read_text())
NAME = C["name"]; OUT = EVAL / "tune3" / "runs" / NAME
DIV, SIGMA, NOISE, CRF = 5, 1.0, 12, 36

def strong(source, directory, *, width, height, fps, frame_count, ffmpeg="ffmpeg"):
    directory.mkdir(parents=True, exist_ok=True)
    clean, degraded = directory / "clean.mp4", directory / "degraded.mp4"
    normalize = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                 f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,fps={fps},setsar=1")
    ev._run_ffmpeg([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(source),
                    "-map", "0:v:0", "-an", "-vf", normalize, "-frames:v", str(frame_count),
                    "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(clean)])
    ev._run_ffmpeg([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(clean),
                    "-map", "0:v:0", "-an", "-vf", vf(DIV, SIGMA, NOISE), "-frames:v", str(frame_count),
                    "-c:v", "libx264", "-crf", str(CRF), "-pix_fmt", "yuv420p", str(degraded)])
    return clean, degraded
ev.prepare_degraded_clip = strong

BASE_SIGMAS = wf.DISTILLED_SIGMAS
def sigmas(n):
    if n == 8: return BASE_SIGMAS
    xs = np.linspace(0, 8, n + 1)
    return tuple(round(float(np.interp(x, range(9), BASE_SIGMAS)), 6) for x in xs)

_orig_build = wf.build_workflow
def build(request, video_name, reference_name=None, previous_name=None, model_files=None):
    g = _orig_build(request, video_name, reference_name, previous_name, model_files)
    g["4"]["inputs"]["strength_model"] = float(C.get("lora", 1.0))
    g["12"]["inputs"]["strength"] = float(C.get("vid_strength", 1.0))
    g["16"]["inputs"]["sigmas"] = ", ".join(str(x) for x in sigmas(int(C.get("steps", 8))))
    if "14" in g:
        g["14"]["inputs"]["strength"] = float(C.get("ref_strength", 1.0))
        g["14"]["inputs"]["frame_idx"] = int(C.get("ref_frame_idx", -1))
        last = "14"
        for i, idx in enumerate(C.get("ref_extra_idx", [])):
            nid = f"3{i}"
            node = json.loads(json.dumps(g["14"]))
            node["inputs"].update(positive=[last, 0], negative=[last, 1], latent=[last, 2], frame_idx=int(idx))
            g[nid] = node; last = nid
        g["17"]["inputs"].update(positive=[last, 0], negative=[last, 1], latents=[last, 2])
    if "23" in g:
        g["23"]["inputs"]["strength"] = float(C.get("kf_strength", 1.0))
        g["23"]["inputs"]["frame_idx"] = int(C.get("kf_idx", 0))
    R = C.get("work_size")
    if R:
        for nid in ("10", "11"):
            g[nid]["inputs"].update(width=int(R[0]), height=int(R[1]))
        g["40"] = {"class_type": "ImageScale", "inputs": {"image": ["18", 0], "upscale_method": "lanczos",
                   "width": request.width, "height": request.height, "crop": "disabled"}}
        g["19"]["inputs"]["images"] = ["40", 0]
    wf.validate_graph(g)
    return g
wf.build_workflow = build; cb.build_workflow = build

_orig_canvas = ev._canvas
def canvas(photo, output, observation, clip, key, width, height):
    e = float(C.get("expand", 1.0)); cm = C.get("color_match", False)
    R = C.get("work_size"); sx = sy = 1.0
    if R:
        sx, sy = R[0] / width, R[1] / height; width, height = int(R[0]), int(R[1])
    if C.get("canvas_align"):
        return canvas_align(photo, output, clip, width, height, sx, sy)
    if e == 1.0 and not cm and not R:
        return _orig_canvas(photo, output, observation, clip, key, width, height)
    from PIL import Image, ImageOps
    from app.reference import read_photo
    img = read_photo(photo)
    bx, by, bw, bh = observation.bbox
    def grow(x, y, w, h, W, H, up):
        cx, cy = x + w / 2, y + h / 2 - up * h
        nw, nh = w * e, h * e
        x0, y0 = max(0, cx - nw / 2), max(0, cy - nh / 2)
        x1, y1 = min(W, cx + nw / 2), min(H, cy + nh / 2)
        return int(x0), int(y0), int(x1), int(y1)
    t = clip["face_bbox"]
    tb = grow(t["x"] * sx, t["y"] * sy, t["width"] * sx, t["height"] * sy, width, height, 0.0)
    # photo box from detector is a tight face box; map it to the (head-sized) clip box the same way
    pb = grow(bx, by, bw, bh, img.width, img.height, 0.0)
    face = ImageOps.fit(img.crop(pb), (tb[2] - tb[0], tb[3] - tb[1]), method=Image.Resampling.LANCZOS)
    if cm:
        import cv2
        cap = cv2.VideoCapture(str(output.parent / "degraded.mp4")); ok, fr = cap.read(); cap.release()
        reg = cv2.cvtColor(fr[tb[1]:tb[3], tb[0]:tb[2]], cv2.COLOR_BGR2LAB).astype(np.float32)
        f = cv2.cvtColor(np.asarray(face)[:, :, ::-1].copy(), cv2.COLOR_BGR2LAB).astype(np.float32)
        for ch in range(3):
            f[..., ch] = (f[..., ch] - f[..., ch].mean()) / (f[..., ch].std() + 1e-6) * reg[..., ch].std() + reg[..., ch].mean()
        face = Image.fromarray(cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)[:, :, ::-1].copy())
    cv = Image.new("RGB", (width, height), (128, 128, 128)); cv.paste(face, (tb[0], tb[1]))
    output.parent.mkdir(parents=True, exist_ok=True); cv.save(output, format="PNG")
    return output
ev._canvas = canvas

def canvas_align(photo, output, clip, width, height, sx, sy):
    """Model card: reference crops sit 'over its subject' on a gray canvas. Instead of a bbox fit,
    similarity-warp the photo so its 5 landmarks land on the subject's frame-0 landmarks, keep a
    head-sized ellipse (grown by canvas_align), gray elsewhere."""
    import cv2
    from app.evaluation import _photo
    ph = _photo(photo)
    base = _first(EVAL / C.get("kf_base", "run-97-strong") / clip["id"] / "without_reference.mp4")
    if (sx, sy) != (1.0, 1.0):
        base = cv2.resize(base, (width, height), interpolation=cv2.INTER_LANCZOS4)
    lp, pb = _land(ph); lf, fb = _land(base)
    M, _ = cv2.estimateAffinePartial2D(lp, lf, method=cv2.LMEDS)
    warped = cv2.warpAffine(ph, M, (width, height), flags=cv2.INTER_AREA, borderValue=(128, 128, 128))
    m = np.zeros(ph.shape[:2], np.float32); x, y, w, h = pb; k = float(C["canvas_align"])
    cv2.ellipse(m, (int(x + w / 2), int(y + h * 0.45)), (int(w * 0.5 * k), int(h * 0.6 * k)), 0, 0, 360, 1.0, -1)
    m = cv2.warpAffine(m, M, (width, height), flags=cv2.INTER_LINEAR)
    m = cv2.GaussianBlur(m, (0, 0), max(2.0, float(fb[2]) * 0.04))[..., None]
    cv = np.clip(128 * (1 - m) + warped * m, 0, 255).astype(np.uint8)
    output.parent.mkdir(parents=True, exist_ok=True); cv2.imwrite(str(output), cv)
    return output

async def facepass(request, backend):
    """Full-frame restore, then a face-crop restore at higher resolution, feathered paste-back.
    Applied identically to every arm (the no-photo arm gets a no-photo crop pass)."""
    import cv2, subprocess, dataclasses
    from PIL import Image
    P = C["facepass"]; N = int(P.get("size", 768)); scale = float(P.get("scale", 1.8))
    cond = request.output.stem; d = request.output.parent / "fp"; d.mkdir(exist_ok=True)
    man = json.loads((EVAL / C.get("manifest", "pilot-97.json")).read_text())
    b = next(c for c in man["clips"] if c["id"] == request.output.parent.name)["face_bbox"]
    S = min(736, int(max(b["width"], b["height"]) * scale) // 2 * 2)
    cx, cy = b["x"] + b["width"] // 2, b["y"] + b["height"] // 2
    x = max(0, min(1280 - S, cx - S // 2)); y = max(0, min(736 - S, cy - S // 2))
    base = d / f"{cond}_base.mp4"
    await backend.restore(dataclasses.replace(request, output=base))
    crop_in = d / f"{cond}_in.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(request.video), "-vf",
                    f"crop={S}:{S}:{x}:{y},scale={N}:{N}:flags=lanczos,setsar=1", "-c:v", "libx264", "-crf", "12",
                    "-pix_fmt", "yuv420p", str(crop_in)], check=True)
    ref = None
    if request.reference is not None:
        ref = d / f"{cond}_ref.png"
        Image.open(request.reference).convert("RGB").crop((x, y, x + S, y + S)).resize((N, N), Image.Resampling.LANCZOS).save(ref)
    face = d / f"{cond}_face.mp4"
    await backend.restore(dataclasses.replace(request, video=crop_in, output=face, reference=ref, width=N, height=N))
    m = np.zeros((S, S), np.float32); k = int(S * float(P.get("feather", 0.12)))
    m[k:S - k, k:S - k] = 1.0; m = cv2.GaussianBlur(m, (0, 0), k / 2.0)[..., None]
    cb_, cf = cv2.VideoCapture(str(base)), cv2.VideoCapture(str(face))
    tmp = d / f"{cond}_paste.mp4"
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1280x736",
                             "-r", str(request.fps), "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(tmp)],
                            stdin=subprocess.PIPE)
    n = 0
    while True:
        ok1, fb = cb_.read(); ok2, ff = cf.read()
        if not ok1: break
        if ok2:
            ff = cv2.resize(ff, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32)
            reg = fb[y:y + S, x:x + S].astype(np.float32)
            fb[y:y + S, x:x + S] = np.clip(reg * (1 - m) + ff * m, 0, 255).astype(np.uint8)
        proc.stdin.write(fb.tobytes()); n += 1
    proc.stdin.close(); proc.wait(); cb_.release(); cf.release()
    if proc.returncode or n != request.frame_count:
        raise RuntimeError(f"paste failed rc={proc.returncode} frames={n}")
    tmp.replace(request.output)
    return request.output

_ENG = None
def _land(img):
    """YuNet 5 landmarks (re, le, nose, rm, lm) + bbox on a BGR image."""
    import cv2
    global _ENG
    if _ENG is None: _ENG = ev.SFaceEngine(ROOT / "models" / "evaluation")
    h, w = img.shape[:2]; sc = min(1.0, 640.0 / max(w, h))
    sm = cv2.resize(img, (max(1, round(w * sc)), max(1, round(h * sc))))
    _ENG.detector.setInputSize((sm.shape[1], sm.shape[0])); _, f = _ENG.detector.detect(sm)
    f = f[np.argmax(f[:, 2] * f[:, 3])].copy(); f[:14] /= sc
    return f[4:14].reshape(5, 2).astype(np.float32), f[:4]

def _first(path):
    import cv2
    cap = cv2.VideoCapture(str(path)); ok, fr = cap.read(); cap.release(); return fr

def make_keyframe(request, clip, cond):
    """Keyframe anchor: landmark-align the photo face onto frame 0 of the no-photo restore,
    LAB colour-match, feathered blend. Written as a 1-frame mp4 for the frame-0 LTXVAddGuide."""
    import cv2, subprocess
    d = request.output.parent; d.mkdir(parents=True, exist_ok=True)
    mode = C["keyframe"]
    if mode == "oracle":
        base = _first(d / "clean.mp4"); comp = base
    elif mode == "file":  # precomputed keyframe (e.g. RestorerID face pasted on the no-photo frame 0), see ridpaste.py
        comp = cv2.imread(str(EVAL / C.get("kf_root", "tune2/rid/kf") / C["kf_dir"] / clip / f"{cond}.png"))
        assert comp is not None, (C["kf_dir"], clip, cond)
    elif mode == "self":
        comp = _first(EVAL / C.get("kf_base", "run-97-strong") / clip / f"{cond}.mp4")
    else:
        base = _first(EVAL / C.get("kf_base", "run-97-strong") / clip / "without_reference.mp4")
        man = json.loads((EVAL / C.get("manifest", "pilot-97.json")).read_text())
        cl = next(c for c in man["clips"] if c["id"] == clip)
        photo_path = EVAL / (cl["reference"] if cond == "correct_reference" else cl["wrong_reference"])
        from app.evaluation import _photo
        photo = _photo(photo_path)
        lp, pb = _land(photo); lf, fb = _land(base)
        M, _ = cv2.estimateAffinePartial2D(lp, lf, method=cv2.LMEDS)
        H, W = base.shape[:2]
        warped = cv2.warpAffine(photo, M, (W, H), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REFLECT)
        m = np.zeros(photo.shape[:2], np.float32)
        x, y, w, h = pb; k = float(C.get("kf_mask", 0.92))
        cv2.ellipse(m, (int(x + w / 2), int(y + h * 0.52)), (int(w * 0.5 * k), int(h * 0.56 * k)), 0, 0, 360, 1.0, -1)
        m = cv2.warpAffine(m, M, (W, H), flags=cv2.INTER_LINEAR)
        sig = max(2.0, float(fb[2]) * float(C.get("kf_feather", 0.07)))
        m = cv2.GaussianBlur(m, (0, 0), sig)[..., None]
        sel = m[..., 0] > 0.5
        a = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB).astype(np.float32); b = cv2.cvtColor(base, cv2.COLOR_BGR2LAB).astype(np.float32)
        for ch in range(3):
            a[..., ch] = (a[..., ch] - a[..., ch][sel].mean()) / (a[..., ch][sel].std() + 1e-6) * b[..., ch][sel].std() + b[..., ch][sel].mean()
        warped = cv2.cvtColor(np.clip(a, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
        comp = np.clip(base * (1 - m) + warped * m, 0, 255).astype(np.uint8)
    png = d / f"{cond}_keyframe.png"; cv2.imwrite(str(png), comp)
    mp4 = d / f"{cond}_keyframe.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(png), "-frames:v", "1", "-r", str(request.fps),
                    "-c:v", "libx264", "-crf", "6", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    return mp4

TIMES = {}
async def adapter(request, backend):
    cond = request.output.stem; clip = request.output.parent.name
    reuse = C.get("reuse_without")
    t = time.monotonic()
    if cond == "without_reference" and reuse:
        src = EVAL / reuse / clip / "without_reference.mp4"
        shutil.copyfile(src, request.output); TIMES[f"{clip}/{cond}"] = 0.0
        return request.output
    import dataclasses
    if C.get("prompts"):
        request = dataclasses.replace(request, prompt=C["prompts"][clip], negative_prompt=C.get("negative", ""))
    if C.get("keyframe") and (request.reference is not None or C.get("kf_none")):
        kf = make_keyframe(request, clip, cond)
        request = dataclasses.replace(request, previous_frames=kf)
    if C.get("facepass"):
        out = await facepass(request, backend)
    else:
        out = await backend.restore(request)
    TIMES[f"{clip}/{cond}"] = round(time.monotonic() - t, 1)
    print(clip, cond, TIMES[f"{clip}/{cond}"], "s", flush=True)
    return out

async def main():
    from app.backends import get_backend
    from app.config import Settings
    s = Settings(); backend = get_backend(s)
    manifest = EVAL / C.get("manifest", "pilot-97.json")
    t0 = time.monotonic()
    rep = await ev.evaluate_experiment(manifest, OUT, backend=backend, model_dir=ROOT / "models" / "evaluation",
                                       backend_mode=s.mode, render_adapter=adapter, ffmpeg=s.ffmpeg)
    rj = OUT / "run.json"; d = json.loads(rj.read_text())
    d["tuning"] = C; d["render_seconds"] = TIMES; d["wall_seconds"] = round(time.monotonic() - t0, 1)
    rj.write_text(json.dumps(d, indent=2))
    for c in rep["clips"]:
        print(c["id"], json.dumps(c["report"]["paired_deltas"]))
    print("wall", d["wall_seconds"])
asyncio.run(main())
