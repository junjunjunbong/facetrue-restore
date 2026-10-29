"""Private local upload, selection, job and download API."""

import asyncio
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.backends import get_backend
from app.media import first_frame, normalize_video
from app.pipeline import run_comparison
from app.reference import BBox, build_reference_canvas, detect_faces, read_photo

router = APIRouter(prefix="/api")
ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
VIDEO_TYPES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def identifier(value: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise HTTPException(404, "Not found")
    return value


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise HTTPException(404, "Item not found")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(path)


def upload_directory(request: Request, upload_id: str) -> Path:
    path = request.app.state.settings.data_dir / "uploads" / identifier(upload_id)
    if not (path / "meta.json").is_file():
        raise HTTPException(404, "Upload not found")
    return path


async def store_upload(file: UploadFile, path: Path, limit: int) -> None:
    total = 0
    try:
        with path.open("xb") as target:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise HTTPException(413, f"Upload exceeds {limit // 1024**2} MB")
                target.write(chunk)
        if total == 0:
            raise HTTPException(422, "File is empty")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.post("/uploads")
async def upload_video(request: Request, video: UploadFile = File(...), deinterlace: bool = Form(False)):
    settings = request.app.state.settings
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in VIDEO_TYPES:
        raise HTTPException(415, "Upload an MP4, MOV, AVI, MKV, M4V, or WebM video")
    upload_id = uuid4().hex
    directory = settings.data_dir / "uploads" / upload_id
    directory.mkdir(parents=True)
    source = directory / ("source" + suffix)
    await store_upload(video, source, settings.upload_limit_mb * 1024**2)
    try:
        info = await asyncio.to_thread(normalize_video, source, directory / "normalized.mp4",
                                        settings.width, settings.height, settings.fps, deinterlace,
                                        settings.max_seconds, settings.ffmpeg, settings.ffprobe)
        if info.frames < 4 * settings.fps:
            raise ValueError("Upload a 4–10 second clip. Use the CLI for 49-frame GPU preflight.")
        await asyncio.to_thread(first_frame, directory / "normalized.mp4", directory / "first.png", settings.ffmpeg)
        faces = await asyncio.to_thread(lambda: detect_faces(read_photo(directory / "first.png")))
    except (ValueError, RuntimeError, OSError) as error:
        raise HTTPException(422, str(error)) from error
    metadata = {"upload_id": upload_id, **asdict(info), "frame_count": info.frames,
                "deinterlace": deinterlace, "faces": [asdict(face) for face in faces],
                "frame_url": f"/api/media/{upload_id}/first.png"}
    save_json(directory / "meta.json", metadata)
    return metadata


@router.post("/uploads/{upload_id}/photo")
async def upload_photo(request: Request, upload_id: str, photo: UploadFile = File(...)):
    directory = upload_directory(request, upload_id)
    photo_id = uuid4().hex
    raw = directory / f"photo-{photo_id}.upload"
    await store_upload(photo, raw, min(request.app.state.settings.upload_limit_mb, 25) * 1024**2)
    try:
        image = await asyncio.to_thread(read_photo, raw)
        target = directory / f"photo-{photo_id}.png"
        image.save(target, format="PNG")
        faces = await asyncio.to_thread(detect_faces, image)
    except (ValueError, OSError) as error:
        raise HTTPException(422, "Cannot decode this photo. Use a JPEG or PNG image under 25 megapixels.") from error
    finally:
        raw.unlink(missing_ok=True)
    metadata = {"photo_id": photo_id, "upload_id": upload_id, "width": image.width, "height": image.height,
                "faces": [asdict(face) for face in faces], "photo_url": f"/api/media/{upload_id}/{target.name}"}
    save_json(directory / f"photo-{photo_id}.json", metadata)
    return metadata


class BoxInput(BaseModel):
    x: int = Field(ge=0, strict=True)
    y: int = Field(ge=0, strict=True)
    width: int = Field(ge=2, strict=True)
    height: int = Field(ge=2, strict=True)

    def box(self) -> BBox:
        return BBox(**self.model_dump())


class CanvasInput(BaseModel):
    upload_id: str
    photo_id: str
    bbox: BoxInput
    photo_bbox: BoxInput | None = None


@router.post("/canvas")
async def create_canvas(request: Request, body: CanvasInput):
    directory = upload_directory(request, body.upload_id)
    photo_id = identifier(body.photo_id)
    read_json(directory / f"photo-{photo_id}.json")
    info = read_json(directory / "meta.json")
    reference_id = uuid4().hex
    output = directory / f"canvas-{reference_id}.png"
    try:
        result = await asyncio.to_thread(build_reference_canvas, directory / f"photo-{photo_id}.png", output,
                                         body.bbox.box(), info["width"], info["height"],
                                         body.photo_bbox.box() if body.photo_bbox else None,
                                         request.app.state.settings.reference_expand)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    metadata = {"reference_id": reference_id, "upload_id": body.upload_id, "photo_id": photo_id,
                "bbox": asdict(result.target_bbox), "photo_bbox": asdict(result.photo_bbox),
                "crop_method": result.crop_method, "frame_idx": -1,
                "canvas_url": f"/api/media/{body.upload_id}/{output.name}"}
    save_json(directory / f"canvas-{reference_id}.json", metadata)
    return metadata


class JobInput(BaseModel):
    upload_id: str
    reference_id: str
    seed: int = Field(default=42, ge=0, le=2**32 - 1, strict=True)
    preset: Literal["neutral", "vhs_1980s", "film_1940s"] = "neutral"
    synthetic: bool = False


async def execute_job(application, body: JobInput, job: dict) -> None:
    settings = application.state.settings
    job_file = settings.data_dir / "jobs" / job["id"] / "job.json"

    def update(fraction: float, message: str) -> None:
        job.update(progress=fraction, message=message, stage=message)
        save_json(job_file, job)

    try:
        async with application.state.gpu_lock:
            job["status"] = "running"
            update(0.01, "Preparing paired comparison")
            source_dir = settings.data_dir / "uploads" / body.upload_id
            outputs = await run_comparison(
                source_dir / "normalized.mp4", source_dir / f"canvas-{body.reference_id}.png",
                settings.data_dir / "outputs" / job["id"], get_backend(settings), settings,
                seed=body.seed, preset=body.preset, synthetic=body.synthetic, progress=update,
            )
            job["outputs"] = {key: f"/api/results/{job['id']}/{path.name}" for key, path in outputs.items()}
            job["status"] = "succeeded"
            update(1.0, "Comparison ready" if settings.mode != "mock" else "Mock comparison ready — input copies only")
    except asyncio.CancelledError:
        job.update(status="failed", error="App stopped during this job. Run it again.")
        save_json(job_file, job)
        raise
    except Exception as error:
        job.update(status="failed", error=f"{type(error).__name__}: {error}"[:1500], message="Processing failed")
        save_json(job_file, job)


@router.post("/jobs", status_code=202)
async def create_job(request: Request, body: JobInput):
    application = request.app
    directory = upload_directory(request, body.upload_id)
    identifier(body.reference_id)
    read_json(directory / f"canvas-{body.reference_id}.json")
    if len(application.state.tasks) >= 4:
        raise HTTPException(429, "Four jobs are already queued or running. Wait for a job to finish.")
    job = {"id": uuid4().hex, "status": "queued", "progress": 0.0, "stage": "Queued", "message": "Queued",
           "created_at": datetime.now(timezone.utc).isoformat(), "mode": application.state.settings.mode,
           "outputs": {}, "error": None, "input": body.model_dump()}
    save_json(application.state.settings.data_dir / "jobs" / job["id"] / "job.json", job)
    task = asyncio.create_task(execute_job(application, body, job))
    application.state.tasks.add(task)
    task.add_done_callback(application.state.tasks.discard)
    return dict(job)


@router.get("/jobs/{job_id}")
def get_job(request: Request, job_id: str):
    return read_json(request.app.state.settings.data_dir / "jobs" / identifier(job_id) / "job.json")


@router.get("/media/{upload_id}/{filename}")
def uploaded_media(request: Request, upload_id: str, filename: str):
    directory = upload_directory(request, upload_id)
    allowed = filename in {"first.png", "normalized.mp4"} or bool(
        re.fullmatch(r"(?:photo|canvas)-[a-f0-9]{32}\.png", filename))
    if not allowed or not (directory / filename).is_file():
        raise HTTPException(404, "Media not found")
    return FileResponse(directory / filename, headers={"Cache-Control": "no-store"})


@router.get("/results/{job_id}/{filename}")
def result_file(request: Request, job_id: str, filename: str):
    job = get_job(request, job_id)
    allowed = {Path(url).name for url in job.get("outputs", {}).values()}
    if job["status"] != "succeeded" or filename not in allowed:
        raise HTTPException(404, "Result not found")
    path = request.app.state.settings.data_dir / "outputs" / identifier(job_id) / filename
    if not path.is_file():
        raise HTTPException(404, "Result was removed")
    return FileResponse(path, headers={"Cache-Control": "no-store"})
