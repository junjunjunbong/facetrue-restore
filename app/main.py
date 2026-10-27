"""Loopback-first FastAPI app. Real inference is opt-in."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import __version__
from app.config import ROOT, Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        settings.create_directories()
        yield

    application = FastAPI(title="FaceTrue Restore", version=__version__, lifespan=lifespan)
    application.state.settings = settings

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
