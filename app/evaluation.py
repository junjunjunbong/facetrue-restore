"""Paired identity evaluation. Mock output is never restoration evidence.

SFace similarity is a diagnostic, not proof of faithful reconstruction. Ground
truth is the clean clip; the conditioning portrait is only a secondary metric.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import math
import statistics
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence


CONDITIONS = ("without_reference", "correct_reference", "wrong_reference")
MODEL_SPECS = {
    "yunet": {
        "filename": "face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "bytes": 232589,
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "license": "MIT",
        "license_url": "https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE",
    },
    "sface": {
        "filename": "face_recognition_sface_2021dec.onnx",
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        "bytes": 38696353,
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "license": "Apache-2.0 (official distribution); training-data provenance unconfirmed",
        "license_url": "https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/LICENSE",
    },
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_model(path: Path, key: str) -> None:
    spec = MODEL_SPECS[key]
    if not path.is_file():
        raise FileNotFoundError(f"Missing {key}: {path}. Run scripts/download_eval_models.py explicitly.")
    if path.stat().st_size != spec["bytes"] or file_sha256(path) != spec["sha256"]:
        raise ValueError(f"{key} model hash/size mismatch: {path}")


def require_real_backend(backend: Any, mode: str) -> None:
    if mode != "comfy" or getattr(backend, "is_mock", False):
        raise ValueError("Mock output cannot be scored as restoration evidence; use a real Comfy backend.")
    if any("mock" in cls.__name__.lower() for cls in type(backend).__mro__):
        raise ValueError("Mock output cannot be scored as restoration evidence.")


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) == 0 or len(a) != len(b):
        raise ValueError("Embedding dimensions differ or are empty")
    if not all(math.isfinite(float(x)) for x in (*a, *b)):
        raise ValueError("Non-finite embedding")
    norm = math.sqrt(sum(float(x) ** 2 for x in a) * sum(float(x) ** 2 for x in b))
    if norm == 0:
        raise ValueError("Zero embedding")
    return max(-1.0, min(1.0, sum(float(x) * float(y) for x, y in zip(a, b)) / norm))


@dataclass(frozen=True)
class FaceObservation:
    embedding: tuple[float, ...] | None = None
    bbox: tuple[float, float, float, float] | None = None
    reason: str | None = None


class FaceEngine(Protocol):
    def observe(self, bgr_image: Any) -> FaceObservation: ...


class SFaceEngine:
    """CPU-only OpenCV inference; no network or model download in constructor."""

    def __init__(self, model_dir: Path, confidence: float = 0.9):
        import cv2

        if not 0 < confidence <= 1:
            raise ValueError("Face confidence must be in (0, 1]")
        paths = {key: Path(model_dir) / str(spec["filename"]) for key, spec in MODEL_SPECS.items()}
        for key, path in paths.items():
            verify_model(path, key)
        self.cv = cv2
        self.detector = cv2.FaceDetectorYN.create(str(paths["yunet"]), "", (320, 320), confidence, 0.3, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(str(paths["sface"]), "")

    def observe(self, bgr_image: Any) -> FaceObservation:
        if bgr_image is None or bgr_image.ndim != 3 or bgr_image.shape[2] != 3:
            return FaceObservation(reason="invalid_image")
        height, width = bgr_image.shape[:2]
        scale = min(1.0, 640.0 / max(width, height))
        small = self.cv.resize(bgr_image, (max(1, round(width * scale)), max(1, round(height * scale))))
        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self.detector.detect(small)
        if faces is None or len(faces) == 0:
            return FaceObservation(reason="no_face")
        if len(faces) != 1:
            return FaceObservation(reason=f"ambiguous_faces:{len(faces)}")
        face = faces[0].copy()
        # Actual rounded resize can differ on each axis.
        face[[0, 2, 4, 6, 8, 10, 12]] *= width / small.shape[1]
        face[[1, 3, 5, 7, 9, 11, 13]] *= height / small.shape[0]
        aligned = self.recognizer.alignCrop(bgr_image, face)
        feature = tuple(float(x) for x in self.recognizer.feature(aligned).copy().reshape(-1))
        try:
            cosine(feature, feature)
        except ValueError:
            return FaceObservation(reason="invalid_embedding")
        return FaceObservation(feature, tuple(float(x) for x in face[:4]))


@dataclass(frozen=True)
class FrameScore:
    frame_index: int
    condition: str
    gt_cosine: float | None
    correct_photo_cosine: float | None = None
    wrong_photo_cosine: float | None = None
    failure_reason: str | None = None


def score_observation(
    frame_index: int, condition: str, clean: FaceObservation, restored: FaceObservation,
    correct_photo: FaceObservation, wrong_photo: FaceObservation,
) -> FrameScore:
    if clean.embedding is None:
        return FrameScore(frame_index, condition, None, failure_reason=f"ground_truth:{clean.reason}")
    if restored.embedding is None:
        return FrameScore(frame_index, condition, None, failure_reason=f"output:{restored.reason}")
    if correct_photo.embedding is None or wrong_photo.embedding is None:
        raise ValueError("Both independent reference photos must have one valid face")
    return FrameScore(
        frame_index, condition, cosine(clean.embedding, restored.embedding),
        cosine(correct_photo.embedding, restored.embedding),
        cosine(wrong_photo.embedding, restored.embedding),
    )


def aggregate_scores(rows: Sequence[FrameScore], min_common_coverage: float = 0.8) -> dict[str, Any]:
    """Use exactly the same valid timestamps in all arms; retain every failure."""
    if not 0 < min_common_coverage <= 1:
        raise ValueError("Minimum coverage must be in (0, 1]")
    if not rows:
        raise ValueError("No sampled frames")
    grouped: dict[int, dict[str, FrameScore]] = {}
    for row in rows:
        if row.condition not in CONDITIONS or row.frame_index < 0:
            raise ValueError("Invalid condition/frame index")
        if row.gt_cosine is not None and (not math.isfinite(row.gt_cosine) or not -1 <= row.gt_cosine <= 1):
            raise ValueError("Invalid cosine score")
        per_frame = grouped.setdefault(row.frame_index, {})
        if row.condition in per_frame:
            raise ValueError("Duplicate condition at the same frame")
        per_frame[row.condition] = row
    if any(set(frame) != set(CONDITIONS) for frame in grouped.values()):
        raise ValueError("Every sampled frame must include all three conditions, including failures")
    common = sorted(i for i, frame in grouped.items() if all(r.gt_cosine is not None for r in frame.values()))
    coverage = len(common) / len(grouped)
    summary = []
    for condition in CONDITIONS:
        all_rows = [frame[condition] for frame in grouped.values()]
        valid = [grouped[i][condition] for i in common]
        reasons: dict[str, int] = {}
        for row in all_rows:
            if row.gt_cosine is None:
                reason = row.failure_reason or "missing_score"
                reasons[reason] = reasons.get(reason, 0) + 1
        item: dict[str, Any] = {
            "condition": condition, "sampled_frames": len(grouped),
            "valid_frames": sum(row.gt_cosine is not None for row in all_rows),
            "common_valid_frames": len(common), "common_coverage": coverage,
            "failure_reasons": reasons,
            "status": "pilot_result" if common and coverage >= min_common_coverage else "inconclusive",
        }
        for name in ("gt_cosine", "correct_photo_cosine", "wrong_photo_cosine"):
            values = [getattr(row, name) for row in valid if getattr(row, name) is not None]
            item[f"{name}_mean"] = statistics.fmean(values) if values else None
            if name == "gt_cosine":
                item["gt_cosine_median"] = statistics.median(values) if values else None
        summary.append(item)
    means = {item["condition"]: item["gt_cosine_mean"] for item in summary}
    deltas = {
        "correct_minus_without": None if not common else means["correct_reference"] - means["without_reference"],
        "correct_minus_wrong": None if not common else means["correct_reference"] - means["wrong_reference"],
    }
    return {"conditions": summary, "common_frame_indices": common, "paired_deltas": deltas,
            "status": summary[0]["status"], "min_common_coverage": min_common_coverage}


def _resolve_file(base: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("Expected a nonempty local media path")
    path = (base / value).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def validate_clip_sources(clip: Mapping[str, Any], base: Path) -> dict[str, Path]:
    if clip.get("independent_reference_confirmed") is not True:
        raise ValueError("Confirm reference photos are separate captures, not frames from the target clip")
    if not isinstance(clip.get("reference_origin"), str) or not clip["reference_origin"].strip():
        raise ValueError("Record reference_origin (separate capture/source provenance)")
    if not isinstance(clip.get("source_rights"), str) or not clip["source_rights"].strip():
        raise ValueError("Record source_rights (source license or permission)")
    identities = [clip.get("identity_id"), clip.get("wrong_identity_id")]
    if any(not isinstance(value, str) or not value.strip() for value in identities) or identities[0] == identities[1]:
        raise ValueError("Record distinct identity_id and wrong_identity_id; pseudonyms are sufficient")
    sources = {key: _resolve_file(base, clip.get(key)) for key in ("hq_video", "reference", "wrong_reference")}
    hashes = [file_sha256(path) for path in sources.values()]
    if len(set(hashes)) != len(hashes):
        raise ValueError("HQ input, correct reference, and wrong reference must be distinct files")
    _validate_box(clip.get("face_bbox"))
    return sources


def _validate_box(box: Any) -> dict[str, float]:
    if not isinstance(box, dict) or set(box) != {"x", "y", "width", "height"}:
        raise ValueError("bbox must contain x, y, width, height in normalized-output pixels")
    values = {key: float(value) for key, value in box.items()}
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("bbox must be finite")
    if values["x"] < 0 or values["y"] < 0 or values["width"] <= 0 or values["height"] <= 0:
        raise ValueError("bbox is outside the image or has no area")
    return values


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-4000:]}")


def prepare_degraded_clip(source: Path, directory: Path, *, width: int, height: int,
                          fps: int, frame_count: int, ffmpeg: str = "ffmpeg") -> tuple[Path, Path]:
    """Deterministic blur/downsample/compression, not a physically accurate VHS simulation."""
    directory.mkdir(parents=True, exist_ok=True)
    clean, degraded = directory / "clean.mp4", directory / "degraded.mp4"
    normalize = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                 f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,fps={fps},setsar=1")
    _run_ffmpeg([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(source),
                 "-map", "0:v:0", "-an", "-vf", normalize, "-frames:v", str(frame_count),
                 "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(clean)])
    low_w, low_h = max(2, (width // 4) // 2 * 2), max(2, (height // 4) // 2 * 2)
    degradation = f"scale={low_w}:{low_h}:flags=area,gblur=sigma=1.2,scale={width}:{height}:flags=bicubic"
    _run_ffmpeg([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(clean),
                 "-map", "0:v:0", "-an", "-vf", degradation, "-frames:v", str(frame_count),
                 "-c:v", "libx264", "-crf", "32", "-pix_fmt", "yuv420p", str(degraded)])
    return clean, degraded


def _video_samples(path: Path, indices: set[int], *, width: int, height: int,
                   fps: int, frame_count: int) -> dict[int, Any]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Cannot decode video: {path}")
    samples = {}
    count = 0
    try:
        observed_fps = capture.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(observed_fps) or abs(observed_fps - fps) > 0.01:
            raise ValueError(f"FPS mismatch for {path}: {observed_fps} vs {fps}")
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame.shape[:2] != (height, width):
                raise ValueError(f"Dimensions mismatch for {path}: {frame.shape[:2]}")
            if count in indices:
                samples[count] = frame
            count += 1
            if count > frame_count:
                raise ValueError(f"Extra frames in {path}; expected {frame_count}")
    finally:
        capture.release()
    if count != frame_count or set(samples) != indices:
        raise ValueError(f"Frame count mismatch for {path}: {count} vs {frame_count}")
    return samples


def _photo(path: Path) -> Any:
    from PIL import Image, ImageOps
    import numpy as np

    with Image.open(path) as image:
        return np.asarray(ImageOps.exif_transpose(image).convert("RGB"))[:, :, ::-1].copy()


def _canvas(photo: Path, output: Path, observation: FaceObservation,
            clip: Mapping[str, Any], key: str, width: int, height: int) -> Path:
    from app.reference import BBox, build_reference_canvas, read_photo

    explicit = clip.get(f"{key}_bbox")
    if explicit is None:
        if observation.embedding is None or observation.bbox is None:
            raise ValueError(f"{key} needs one detectable face or an explicit photo bbox")
        explicit = dict(zip(("x", "y", "width", "height"), observation.bbox))
        photo_width, photo_height = read_photo(photo).size
        x, y = max(0, math.floor(explicit["x"])), max(0, math.floor(explicit["y"]))
        right = min(photo_width, math.ceil(explicit["x"] + explicit["width"]))
        bottom = min(photo_height, math.ceil(explicit["y"] + explicit["height"]))
        explicit = {"x": x, "y": y, "width": right - x, "height": bottom - y}
    photo_box = _validate_box(explicit)
    target_box = _validate_box(clip["face_bbox"])
    if any(value != int(value) for value in (*target_box.values(), *photo_box.values())):
        raise ValueError("Manually selected bboxes must use integer pixels")
    target_box = {key: int(value) for key, value in target_box.items()}
    photo_box = {key: int(value) for key, value in photo_box.items()}
    build_reference_canvas(photo, output, BBox(**target_box), width, height, photo_bbox=BBox(**photo_box))
    if not output.is_file():
        raise RuntimeError("Reference canvas builder did not produce a file")
    return output


def _observe_photo(engine: FaceEngine, image: Any, box: Any) -> FaceObservation:
    if box is None:
        return engine.observe(image)
    box = _validate_box(box)
    x, y = int(box["x"]), int(box["y"])
    right, bottom = math.ceil(box["x"] + box["width"]), math.ceil(box["y"] + box["height"])
    if right > image.shape[1] or bottom > image.shape[0]:
        raise ValueError("Photo bbox exceeds image dimensions")
    return engine.observe(image[y:bottom, x:right])


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty evaluation table")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def _validate_experiment(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if manifest.get("version") != 1 or not isinstance(manifest.get("clips"), list) or not manifest["clips"]:
        raise ValueError("Expected a version:1 manifest with a nonempty clips list")
    defaults = {"width": 1280, "height": 736, "fps": 24, "frame_count": 97,
                "sample_every": 8, "seed": 42, "steps": 8, "min_common_coverage": 0.8}
    settings = {key: manifest.get(key, value) for key, value in defaults.items()}
    for key in defaults.keys() - {"min_common_coverage"}:
        if not isinstance(settings[key], int) or isinstance(settings[key], bool):
            raise ValueError(f"{key} must be an integer")
    if any(not 128 <= settings[key] <= 1920 or settings[key] % 32 for key in ("width", "height")):
        raise ValueError("Evaluation dimensions must be multiples of 32 between 128 and 1920")
    if not 8 <= settings["fps"] <= 60 or not 1 <= settings["frame_count"] <= settings["fps"] * 10:
        raise ValueError("Evaluation supports up to 10 seconds at 8-60 FPS")
    if settings["sample_every"] < 1 or not 0 <= settings["seed"] <= 2**32 - 1 or settings["steps"] != 8:
        raise ValueError("Invalid sample interval or seed; the Restore distilled workflow requires exactly 8 steps")
    if not 0 < float(settings["min_common_coverage"]) <= 1:
        raise ValueError("Minimum coverage must be in (0, 1]")
    ids = [clip.get("id") for clip in manifest["clips"]]
    if any(not isinstance(value, str) or not value or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in value) for value in ids):
        raise ValueError("Clip ids must use ASCII letters, digits, underscore or hyphen")
    if len(set(ids)) != len(ids):
        raise ValueError("Clip ids must be unique")
    return settings


async def evaluate_experiment(
    manifest_path: Path, output_dir: Path, *, backend: Any, model_dir: Path,
    backend_mode: str = "comfy", render_adapter: Callable[[Any, Any], Awaitable[Path]] | None = None,
    ffmpeg: str = "ffmpeg", engine: FaceEngine | None = None,
) -> dict[str, Any]:
    """Normalize, deliberately degrade, restore all arms, and score against HQ.

    render_adapter(request, backend) may delegate to the 97/17 long-clip runner.
    Without an adapter only the 49- and 97-frame hardware preflight is supported.
    The injectable engine is for control-flow tests; the public CLI uses SFace.
    """
    from app.backends import RestoreRequest

    require_real_backend(backend, backend_mode)
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cfg = _validate_experiment(manifest)
    if render_adapter is None and cfg["frame_count"] not in (49, 97):
        raise ValueError("Direct backend evaluation needs 49/97 frames; supply the chunked render_adapter for longer clips")
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Use a new empty evaluation output directory to preserve prior evidence")
    for clip in manifest["clips"]:
        validate_clip_sources(clip, manifest_path.parent)
    face_engine = engine or SFaceEngine(model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run: dict[str, Any] = {
        "version": 1, "status": "running", "backend_mode": backend_mode,
        "backend_class": type(backend).__name__, "synthetically_degraded": True,
        "evidence_kind": "control_flow_test" if engine is not None else "real_model_pilot",
        "settings": cfg, "model_specs": MODEL_SPECS,
        "manifest_sha256": file_sha256(manifest_path), "manifest": manifest,
        "degradation": {"downscale_divisor": 4, "gaussian_sigma": 1.2, "h264_crf": 32},
        "metric": "SFace cosine to corresponding clean HQ frame, paired common timestamps",
        "limitations": ["Cosine is a diagnostic, not proof of faithful reconstruction.",
                        "Separate-capture provenance is operator-confirmed; hashes cannot establish identity.",
                        "Nearby video frames are not independent statistical samples."],
        "clips": [],
    }
    _atomic_json(output_dir / "run.json", run)
    frame_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    try:
        for clip in manifest["clips"]:
            sources = validate_clip_sources(clip, manifest_path.parent)
            clip_dir = output_dir / clip["id"]
            clip_dir.mkdir()
            photos = {key: _photo(sources[key]) for key in ("reference", "wrong_reference")}
            photo_observations = {key: _observe_photo(face_engine, photo, clip.get(f"{key}_bbox"))
                                  for key, photo in photos.items()}
            for key, observation in photo_observations.items():
                if observation.embedding is None:
                    raise ValueError(f"{clip['id']} {key}: {observation.reason}. Supply a clear single-person photo.")
            clean, degraded = await asyncio.to_thread(
                prepare_degraded_clip, sources["hq_video"], clip_dir, width=cfg["width"],
                height=cfg["height"], fps=cfg["fps"], frame_count=cfg["frame_count"], ffmpeg=ffmpeg,
            )
            indices = set(range(0, cfg["frame_count"], cfg["sample_every"])) | {cfg["frame_count"] - 1}
            video_args = {key: cfg[key] for key in ("width", "height", "fps", "frame_count")}
            clean_frames = _video_samples(clean, indices, **video_args)
            _video_samples(degraded, {0}, **video_args)
            # Exact decoded-pixel leakage check catches exported target frames, not all re-encodings.
            for key, photo in photos.items():
                import numpy as np
                if any(photo.shape == frame.shape and np.array_equal(photo, frame) for frame in clean_frames.values()):
                    raise ValueError(f"{key} matches a sampled clean frame; use a separate photograph")
            canvases = {
                "without_reference": None,
                "correct_reference": _canvas(sources["reference"], clip_dir / "correct_canvas.png",
                    photo_observations["reference"], clip, "reference", cfg["width"], cfg["height"]),
                "wrong_reference": _canvas(sources["wrong_reference"], clip_dir / "wrong_canvas.png",
                    photo_observations["wrong_reference"], clip, "wrong_reference", cfg["width"], cfg["height"]),
            }
            outputs: dict[str, Path] = {}
            for condition in CONDITIONS:
                request = RestoreRequest(
                    video=degraded, output=clip_dir / f"{condition}.mp4", reference=canvases[condition],
                    seed=cfg["seed"], steps=cfg["steps"], **video_args,
                    prompt=manifest.get("prompt", "Restore this archival home movie with natural detail and consistent faces."),
                    negative_prompt=manifest.get("negative_prompt", ""),
                )
                result = await (render_adapter(request, backend) if render_adapter else backend.restore(request))
                outputs[condition] = Path(result).resolve()
                if not outputs[condition].is_file():
                    raise RuntimeError(f"Renderer did not produce {condition}")
            samples = {condition: _video_samples(path, indices, **video_args) for condition, path in outputs.items()}
            scored: list[FrameScore] = []
            for index in sorted(indices):
                clean_observation = face_engine.observe(clean_frames[index])
                for condition in CONDITIONS:
                    scored.append(score_observation(index, condition, clean_observation,
                        face_engine.observe(samples[condition][index]),
                        photo_observations["reference"], photo_observations["wrong_reference"]))
            report = aggregate_scores(scored, cfg["min_common_coverage"])
            clip_result = {
                "id": clip["id"], "status": report["status"], "report": report,
                "source_hashes": {key: file_sha256(path) for key, path in sources.items()},
                "normalized_hq_sha256": file_sha256(clean), "degraded_sha256": file_sha256(degraded),
                "outputs": {key: {"path": str(path), "sha256": file_sha256(path)} for key, path in outputs.items()},
            }
            run["clips"].append(clip_result)
            frame_rows.extend({"clip_id": clip["id"], **asdict(row)} for row in scored)
            summary_rows.extend({"clip_id": clip["id"], "seed": cfg["seed"], **row, **report["paired_deltas"]}
                                for row in report["conditions"])
            _atomic_json(output_dir / "run.json", run)
            _write_csv(output_dir / "frames.csv", frame_rows)
            _write_csv(output_dir / "summary.csv", summary_rows)
        run["status"] = "complete"
    except Exception as exc:
        run["status"] = "failed"
        run["failure"] = f"{type(exc).__name__}: {exc}"
        _atomic_json(output_dir / "run.json", run)
        raise
    _atomic_json(output_dir / "run.json", run)
    return run
