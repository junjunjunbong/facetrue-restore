"""Loopback-first FastAPI app. Real inference is opt-in."""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import ROOT, Settings, get_settings
from app.api import router, save_json


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        settings.create_directories()
        application.state.tasks = set()
        application.state.gpu_lock = asyncio.Semaphore(1)
        for job_file in (settings.data_dir / "jobs").glob("*/job.json"):
            try:
                job = json.loads(job_file.read_text())
                if job.get("status") in {"queued", "running"}:
                    job.update(status="failed", error="App restarted during this job. Run it again.")
                    save_json(job_file, job)
            except (ValueError, OSError):
                continue
        try:
            yield
        finally:
            tasks = list(application.state.tasks)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    application = FastAPI(title="FaceTrue Restore", version=__version__, lifespan=lifespan)
    application.state.settings = settings
    application.include_router(router)
    application.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")

    @application.get("/api/health")
    def health():
        return {"status": "ok", "mode": settings.mode, "version": __version__, "gpu_checked": False}

    @application.get("/api/config")
    def public_config():
        return {
            "mode": settings.mode,
            "mock_notice": "MOCK: input copies only. No AI restoration or identity evaluation.",
            "width": settings.width, "height": settings.height, "fps": settings.fps,
            "max_seconds": settings.max_seconds, "seed": settings.seed, "steps": settings.steps,
        }

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "app" / "static" / "index.html")

    return application


app = create_app()
