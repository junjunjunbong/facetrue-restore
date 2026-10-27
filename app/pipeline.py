"""Sequential paired restoration: identical source/settings/seeds, separate histories."""

import asyncio
import hashlib
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from PIL import Image

from app.backends import RestoreBackend, RestoreRequest
from app.chunking import extract_chunk, extract_previous_tail, plan_chunks, stitch_videos
from app.config import Settings
from app.media import NEGATIVE_NOTICE, PRESETS, mux_original_audio, probe_video

Progress = Callable[[float, str], None]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def _progress(callback: Progress | None, value: float, message: str) -> None:
    if callback is not None:
        callback(value, message)


async def restore_video(
    video: Path, reference: Path | None, output: Path, backend: RestoreBackend, settings: Settings,
    seed: int = 42, negative_prompt: str = "", prompt: str = "Restore this archival home movie with natural detail and consistent faces.",
    progress: Progress | None = None,
) -> Path:
    if output.exists():
        raise FileExistsError("Use a new output path; existing results are not overwritten")
    info = await asyncio.to_thread(probe_video, video, settings.ffprobe, True)
    if (info.width, info.height) != (settings.width, settings.height) or abs(info.fps - settings.fps) > 0.01:
        raise ValueError("Normalize the video to the configured dimensions and fps before restoring")
    if info.frames > round(settings.max_seconds * settings.fps) + 1:
        raise ValueError("Video exceeds the MVP duration limit")
    if not 0 <= seed < 2**32:
        raise ValueError("Invalid seed")
    if reference is not None:
        with Image.open(reference) as canvas:
            if canvas.size != (settings.width, settings.height):
                raise ValueError("Reference canvas must match normalized video dimensions")
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent / f"{output.stem}-chunks"
    if work.exists() and any(work.iterdir()):
        raise FileExistsError("Use a new output path; a previous run already uses this chunk directory")
    work.mkdir(exist_ok=True)
    chunks = plan_chunks(info.frames)
    restored: list[Path] = []
    records = []
    for chunk in chunks:
        _progress(progress, chunk.index / len(chunks), f"Restoring window {chunk.index + 1}/{len(chunks)}")
        source = await asyncio.to_thread(extract_chunk, video, work / f"input-{chunk.index:03}.mp4",
                                         chunk, settings.fps, settings.ffmpeg)
        previous = None
        if restored:
            previous = await asyncio.to_thread(extract_previous_tail, restored[-1], work / f"prefix-{chunk.index:03}.mp4",
                                               chunks[chunk.index - 1].model_frames, settings.fps, settings.ffmpeg)
            tail = await asyncio.to_thread(probe_video, previous, settings.ffprobe, True)
            if tail.frames != 17:
                raise ValueError("Prefix must contain exactly 17 restored frames")
        request = RestoreRequest(video=source, output=work / f"restored-{chunk.index:03}.mp4",
                                 reference=reference, previous_frames=previous,
                                 seed=(seed + chunk.index) % 2**32, steps=settings.steps,
                                 width=settings.width, height=settings.height, fps=settings.fps,
                                 frame_count=chunk.model_frames, prompt=prompt, negative_prompt=negative_prompt)
        start = time.monotonic()
        generated = await backend.restore(request)
        actual = await asyncio.to_thread(probe_video, generated, settings.ffprobe, True)
        if (actual.frames, actual.width, actual.height) != (chunk.model_frames, info.width, info.height):
            raise ValueError(f"Window {chunk.index} returned wrong frame count or dimensions")
        if abs(actual.fps - info.fps) > 0.01:
            raise ValueError(f"Window {chunk.index} returned wrong fps")
        restored.append(generated)
        records.append({**asdict(chunk), "seed": request.seed, "seconds": round(time.monotonic() - start, 3),
                        "has_reference": reference is not None, "prefix_frames": 17 if previous else 0})
    silent = await asyncio.to_thread(stitch_videos, restored, chunks, work / "stitched.mp4",
                                     info.frames, settings.fps, settings.ffmpeg, settings.ffprobe)
    await asyncio.to_thread(mux_original_audio, silent, video, output, info.frames, settings.fps, settings.ffmpeg)
    final_info = await asyncio.to_thread(probe_video, output, settings.ffprobe, True)
    if final_info.frames != info.frames:
        raise ValueError("Final output frame count changed while preserving audio")
    output.with_suffix(".render.json").write_text(json.dumps({
        "mode": settings.mode, "mock": settings.mode == "mock", "input_sha256": sha256_file(video),
        "reference_sha256": sha256_file(reference) if reference else None,
        "frames": info.frames, "fps": info.fps, "width": info.width, "height": info.height,
        "seed": seed, "steps": settings.steps, "cfg": 1, "tile": [960, 544],
        "prompt": prompt, "negative_prompt": negative_prompt, "negative_notice": NEGATIVE_NOTICE,
        "chunks": records, "vram_peak_bytes": None, "memory_measurement": "not measured",
    }, indent=2), encoding="utf-8")
    _progress(progress, 1.0, "Restoration stream complete")
    return output


async def run_comparison(
    video: Path, reference: Path, output_dir: Path, backend: RestoreBackend, settings: Settings,
    seed: int | None = None, preset: str = "neutral", synthetic: bool = False,
    progress: Progress | None = None,
) -> dict[str, Path]:
    from app.exports import export_comparisons, label_mock_video

    if preset not in PRESETS:
        raise ValueError("Unknown period preset")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Use an empty output directory to preserve previous comparison evidence")
    seed = settings.seed if seed is None else seed
    output_dir.mkdir(parents=True, exist_ok=True)
    original = output_dir / "original.mp4"
    await asyncio.to_thread(shutil.copyfile, video, original)
    spec = PRESETS[preset]
    prompt = "Restore this archival home movie with natural detail and consistent faces. " + spec["positive"]
    output = {"original": original}
    for index, (label, canvas) in enumerate((("without", None), ("with", reference))):
        filename = ("mock-" if settings.mode == "mock" else "") + label + "-photo.mp4"
        output[label] = await restore_video(
            video, canvas, output_dir / filename, backend, settings, seed=seed,
            prompt=prompt, negative_prompt=spec["negative"],
            progress=lambda fraction, message, i=index, name=label: _progress(
                progress, 0.05 + 0.4 * i + 0.4 * fraction, f"{name.title()} photo: {message}"),
        )
    _progress(progress, 0.87, "Exporting synchronized comparisons")
    info = await asyncio.to_thread(probe_video, video, settings.ffprobe, True)
    render_records = [output[key].with_suffix(".render.json").name for key in ("without", "with")]
    if settings.mode == "mock":
        for key in ("without", "with"):
            output[key] = await asyncio.to_thread(label_mock_video, output[key],
                output_dir / f"mock-{key}-photo-labeled.mp4", settings.fps, info.frames,
                settings.ffmpeg, settings.ffprobe)
    exports = await asyncio.to_thread(export_comparisons, original, output["without"], output["with"],
                                      output_dir, settings.fps, info.frames, settings.mode == "mock", synthetic,
                                      settings.ffmpeg, settings.ffprobe)
    output.update(exports)
    manifest = output_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "mode": settings.mode, "mock": settings.mode == "mock", "synthetically_degraded": synthetic,
        "quality_evidence": False, "notice": "Mock copies are not restoration evidence." if settings.mode == "mock"
            else "Generative reconstruction. Identity improvement requires separate paired evaluation.",
        "source_sha256": sha256_file(video), "reference_canvas_sha256": sha256_file(reference),
        "frames": info.frames, "fps": info.fps, "width": info.width, "height": info.height,
        "seed": seed, "per_window_seeds": [(seed + c.index) % 2**32 for c in plan_chunks(info.frames)],
        "steps": settings.steps, "cfg": 1, "preset": preset, "negative_notice": NEGATIVE_NOTICE,
        "outputs": {key: path.name for key, path in output.items()},
        "render_records": render_records,
    }, indent=2), encoding="utf-8")
    output["manifest"] = manifest
    _progress(progress, 1.0, "Comparison ready")
    return output
