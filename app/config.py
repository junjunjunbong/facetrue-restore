"""Explicit configuration; importing the app never contacts a GPU or downloads weights."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_prefix="FACETRUE_", extra="ignore")

    mode: Literal["mock", "comfy"] = "mock"
    data_dir: Path = ROOT / "data"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1024, le=65535)
    comfyui_url: HttpUrl = Field(default="http://127.0.0.1:8188", validation_alias="COMFYUI_URL")
    comfy_proxy_url: HttpUrl = Field(default="http://127.0.0.1:8189", validation_alias="COMFY_PROXY_URL")
    width: int = Field(default=1280, ge=128, le=1920)
    height: int = Field(default=736, ge=128, le=1920)
    fps: int = Field(default=24, ge=8, le=60)
    max_seconds: float = Field(default=10, gt=0, le=10)
    upload_limit_mb: int = Field(default=256, ge=1, le=2048)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    steps: int = Field(default=8, ge=1, le=50)
    job_timeout_seconds: int = Field(default=7200, ge=30, le=86400)
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"

    @field_validator("width", "height")
    @classmethod
    def multiple_of_32(cls, value: int) -> int:
        if value % 32:
            raise ValueError("Model dimensions must be multiples of 32")
        return value

    @field_validator("data_dir")
    @classmethod
    def absolute_data_dir(cls, value: Path) -> Path:
        return (ROOT / value).resolve() if not value.is_absolute() else value.resolve()

    def create_directories(self) -> None:
        for directory in ("uploads", "jobs", "outputs"):
            (self.data_dir / directory).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
