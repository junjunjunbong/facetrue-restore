"""Backend contract and a deliberately non-restoring offline mock."""

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RestoreRequest:
    video: Path
    output: Path
    seed: int = 42
    steps: int = 8
    reference: Path | None = None
    previous_frames: Path | None = None
    width: int = 1280
    height: int = 736
    fps: int = 24
    frame_count: int = 97
    negative_prompt: str = ""
    prompt: str = "Restore this archival home movie with natural detail and consistent faces."


class RestoreBackend(Protocol):
    async def restore(self, request: RestoreRequest) -> Path: ...


class MockBackend:
    """Copy input bytes. No identity edits, AI restoration, or quality claims."""

    async def restore(self, request: RestoreRequest) -> Path:
        if not request.video.is_file():
            raise FileNotFoundError("Input video does not exist")
        if request.video.resolve() == request.output.resolve():
            raise ValueError("Output must differ from input")
        request.output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copyfile, request.video, request.output)
        return request.output
