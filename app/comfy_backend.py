"""Official Comfy SDK adapter for a loopback proxy and a separate GPU PC.

SDK 0.5.0 resolves its base URL and credential from the process environment at
construction. Scope that environment change to the synchronous constructor; no
network operation runs inside it and the caller's environment is restored.
"""

import asyncio
import os
import tempfile
import threading
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from .backends import RestoreRequest
from .workflow import (
    IMAGE_INPUT,
    OUTPUT_NODE_ID,
    PREVIOUS_NODE_ID,
    REFERENCE_NODE_ID,
    VIDEO_INPUT,
    VIDEO_NODE_ID,
    build_workflow,
)

_SDK_ENV_LOCK = threading.Lock()


class ComfyBackendError(RuntimeError):
    """An actionable backend failure; never silently switch to mock output."""


class ComfyBackendUnavailable(ComfyBackendError):
    pass


class ComfyJobFailed(ComfyBackendError):
    pass


class ComfyJobTimeout(ComfyBackendError):
    pass


class ComfyOutputError(ComfyBackendError):
    pass


def _loopback_proxy_url(value: object) -> str:
    url = str(value).strip().rstrip("/")
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path
    ):
        raise ValueError(
            "COMFY_PROXY_URL must be an explicit loopback HTTP(S) URL, "
            "for example http://127.0.0.1:8189. Set COMFYUI_URL to the GPU PC."
        )
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("COMFY_PROXY_URL has an invalid port") from exc
    return url


def init_comfy_session(settings):
    """Construct an AsyncComfy without cloud fallback or inherited API keys."""
    proxy_url = _loopback_proxy_url(settings.comfy_proxy_url)
    try:
        from comfy_sdk import AsyncComfy
    except ImportError as exc:
        raise ComfyBackendUnavailable(
            "Install requirements-comfy.txt to use the ComfyUI backend."
        ) from exc
    overrides = {
        "COMFY_BASE_URL": proxy_url,
        "COMFY_API_KEY": "",
        # This app never calls Router. Keep its unused surface local as well.
        "COMFY_ROUTER_BASE_URL": proxy_url,
    }
    with _SDK_ENV_LOCK:
        previous = {key: os.environ.get(key) for key in overrides}
        try:
            os.environ.update(overrides)
            return AsyncComfy(timeout=120.0, client_info="facetrue-restore")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


async def _cancel_best_effort(job) -> None:
    # A timeout does not cancel GPU work by itself. Ask to cancel the specific
    # job, never interrupt every job in the user's ComfyUI queue.
    with suppress(Exception):
        await asyncio.wait_for(job.cancel(), timeout=10.0)


class ComfyBackend:
    def __init__(self, settings):
        self.settings = settings
        self.proxy_url = _loopback_proxy_url(settings.comfy_proxy_url)
        self.job_ids: list[str] = []

    async def restore(self, request: RestoreRequest) -> Path:
        inputs = [request.video, request.reference, request.previous_frames]
        for path in inputs:
            if path is not None and not path.is_file():
                raise FileNotFoundError("A restoration input file does not exist")
            if path is not None and path.resolve() == request.output.resolve():
                raise ValueError("Output must differ from every input")
        if request.output.suffix.lower() != ".mp4":
            raise ValueError("Restoration output must have an .mp4 extension")

        # Build/validate before opening a client or uploading any private file.
        graph = build_workflow(
            request,
            video_name=request.video.name,
            reference_name=request.reference.name if request.reference else None,
            previous_name=request.previous_frames.name if request.previous_frames else None,
        )
        async with init_comfy_session(self.settings) as client:
            workflow = client.workflows.from_json(graph)
            workflow.set_input(VIDEO_NODE_ID, VIDEO_INPUT, client.assets.from_file(request.video))
            if request.reference is not None:
                workflow.set_input(
                    REFERENCE_NODE_ID, IMAGE_INPUT, client.assets.from_file(request.reference)
                )
            if request.previous_frames is not None:
                workflow.set_input(
                    PREVIOUS_NODE_ID, VIDEO_INPUT, client.assets.from_file(request.previous_frames)
                )
            try:
                # Do not pass api_key or metadata: no partner nodes, and the
                # local proxy does not accept SDK metadata label maps.
                job = await client.submit(workflow, idempotency_key=str(uuid4()))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise ComfyBackendUnavailable(
                    "ComfyUI submission failed. Check the local proxy, GPU PC connection, "
                    "installed nodes, and model filenames."
                ) from exc
            self.job_ids.append(str(job.id))
            try:
                await job.wait(timeout=self.settings.job_timeout_seconds)
            except TimeoutError as exc:
                await _cancel_best_effort(job)
                raise ComfyJobTimeout(
                    "ComfyUI job exceeded the configured timeout; cancellation was requested."
                ) from exc
            except asyncio.CancelledError:
                await _cancel_best_effort(job)
                raise
            except Exception as exc:
                await _cancel_best_effort(job)
                raise ComfyBackendUnavailable(
                    "Lost contact with the ComfyUI job; cancellation was requested."
                ) from exc
            if job.status != "succeeded":
                raise ComfyJobFailed(
                    f"ComfyUI job ended with status {job.status}; inspect the GPU ComfyUI log."
                )

            outputs = [
                output for output in job.get_outputs(OUTPUT_NODE_ID)
                if Path(output.name).suffix.lower() == ".mp4"
            ]
            if len(outputs) != 1:
                raise ComfyOutputError("The SaveVideo node did not return exactly one MP4 output")
            request.output.parent.mkdir(parents=True, exist_ok=True)
            fd, filename = tempfile.mkstemp(
                prefix=f".{request.output.stem}-", suffix=".mp4", dir=request.output.parent
            )
            os.close(fd)
            temporary = Path(filename)
            try:
                await outputs[0].to_file(temporary)
                if not temporary.is_file() or temporary.stat().st_size == 0:
                    raise ComfyOutputError("ComfyUI returned an empty MP4 output")
                # Full stream/frame verification belongs to the pipeline's
                # ffprobe check, before a result becomes downloadable.
                temporary.replace(request.output)
            except asyncio.CancelledError:
                raise
            except ComfyOutputError:
                raise
            except Exception as exc:
                raise ComfyOutputError("Could not download the ComfyUI MP4 output") from exc
            finally:
                temporary.unlink(missing_ok=True)
        return request.output
