import os
import sys
from types import SimpleNamespace

import pytest

from app.backends import RestoreRequest
from app.comfy_backend import (
    ComfyBackend, ComfyBackendUnavailable, ComfyJobFailed, ComfyJobTimeout,
    ComfyOutputError, init_comfy_session,
)
from app.config import Settings


@pytest.fixture
def sdk(monkeypatch):
    state = SimpleNamespace(
        paths=[], submissions=[], environment=None, canceled=False,
        status="succeeded", fail_submit=False, timeout=False,
        names=["restored.mp4"], payload=b"test output bytes",
    )

    class Workflow:
        def __init__(self, graph):
            self.json = graph

        def set_input(self, node, field, value):
            self.json[node]["inputs"][field] = value

    class Output:
        def __init__(self, name):
            self.name = name

        async def to_file(self, path):
            path.write_bytes(state.payload)

    class Job:
        id = "test-job"

        @property
        def status(self):
            return state.status

        async def wait(self, timeout):
            state.wait_timeout = timeout
            if state.timeout:
                raise TimeoutError("still running")

        async def cancel(self):
            state.canceled = True

        def get_outputs(self, node):
            assert node == "20"
            return [Output(name) for name in state.names]

    class Client:
        def __init__(self, **kwargs):
            state.environment = {key: os.environ.get(key) for key in (
                "COMFY_BASE_URL", "COMFY_API_KEY", "COMFY_ROUTER_BASE_URL"
            )}
            self.workflows = SimpleNamespace(from_json=Workflow)
            self.assets = SimpleNamespace(from_file=self.asset)

        def asset(self, path):
            state.paths.append(path)
            return {"asset_handle": str(path)}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def submit(self, workflow, **kwargs):
            state.submissions.append((workflow.json, kwargs))
            if state.fail_submit:
                raise ConnectionError("offline")
            return Job()

    monkeypatch.setitem(sys.modules, "comfy_sdk", SimpleNamespace(AsyncComfy=Client))
    return state


def inputs(tmp_path, reference=False, previous=False):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"input")
    photo = tmp_path / "reference.png" if reference else None
    prefix = tmp_path / "previous.mp4" if previous else None
    for path in (photo, prefix):
        if path:
            path.write_bytes(b"fixture")
    return RestoreRequest(
        source, tmp_path / "result.mp4", seed=1234,
        reference=photo, previous_frames=prefix,
    )


def config(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, mode="comfy")


async def test_sdk_uploads_paths_and_preserves_seed(tmp_path, sdk):
    request = inputs(tmp_path, reference=True, previous=True)
    backend = ComfyBackend(config(tmp_path))
    result = await backend.restore(request)
    graph, options = sdk.submissions[0]
    assert result.read_bytes() == sdk.payload
    assert sdk.paths == [request.video, request.reference, request.previous_frames]
    assert graph["17"]["inputs"]["seed"] == 1234
    assert graph["8"]["inputs"]["file"]["asset_handle"] == str(request.video)
    assert graph["13"]["inputs"]["image"]["asset_handle"] == str(request.reference)
    assert graph["21"]["inputs"]["file"]["asset_handle"] == str(request.previous_frames)
    assert set(options) == {"idempotency_key"}
    assert backend.job_ids == ["test-job"]


async def test_no_reference_has_no_reference_asset(tmp_path, sdk):
    request = inputs(tmp_path)
    await ComfyBackend(config(tmp_path)).restore(request)
    assert sdk.paths == [request.video]
    assert "13" not in sdk.submissions[0][0]


def test_sdk_environment_is_local_and_restored(tmp_path, monkeypatch, sdk):
    original = {
        "COMFY_BASE_URL": "https://cloud.comfy.org",
        "COMFY_API_KEY": "never-send-this-secret",
        "COMFY_ROUTER_BASE_URL": "https://api.comfy.org",
    }
    for key, value in original.items():
        monkeypatch.setenv(key, value)
    init_comfy_session(config(tmp_path))
    assert sdk.environment == {
        "COMFY_BASE_URL": "http://127.0.0.1:8189",
        "COMFY_API_KEY": "",
        "COMFY_ROUTER_BASE_URL": "http://127.0.0.1:8189",
    }
    assert {key: os.environ[key] for key in original} == original


@pytest.mark.parametrize("url", ["", "https://cloud.comfy.org", "http://192.168.1.2:8189", "http://u:p@localhost:8189"])
def test_cloud_and_nonlocal_proxy_rejected(url, sdk):
    with pytest.raises(ValueError, match="loopback"):
        ComfyBackend(SimpleNamespace(comfy_proxy_url=url))
    assert sdk.environment is None


async def test_timeout_requests_job_cancel_and_creates_no_output(tmp_path, sdk):
    request = inputs(tmp_path)
    sdk.timeout = True
    with pytest.raises(ComfyJobTimeout, match="timeout"):
        await ComfyBackend(config(tmp_path)).restore(request)
    assert sdk.canceled and not request.output.exists()


async def test_failed_job_never_downloads_or_falls_back(tmp_path, sdk):
    request = inputs(tmp_path)
    sdk.status = "failed"
    with pytest.raises(ComfyJobFailed):
        await ComfyBackend(config(tmp_path)).restore(request)
    assert not request.output.exists()


async def test_proxy_offline_is_actionable(tmp_path, sdk):
    sdk.fail_submit = True
    request = inputs(tmp_path)
    with pytest.raises(ComfyBackendUnavailable, match="proxy"):
        await ComfyBackend(config(tmp_path)).restore(request)
    assert not request.output.exists()


@pytest.mark.parametrize("names,payload", [([], b"ok"), (["image.png"], b"ok"), (["a.mp4", "b.mp4"], b"ok"), (["a.mp4"], b"")])
async def test_missing_or_empty_mp4_rejected(tmp_path, sdk, names, payload):
    request = inputs(tmp_path)
    sdk.names, sdk.payload = names, payload
    with pytest.raises(ComfyOutputError):
        await ComfyBackend(config(tmp_path)).restore(request)
    assert not request.output.exists()
    assert not list(tmp_path.glob(".result-*.mp4"))


async def test_input_overwrite_rejected_before_sdk(tmp_path, sdk):
    request = inputs(tmp_path)
    with pytest.raises(ValueError, match="differ"):
        await ComfyBackend(config(tmp_path)).restore(RestoreRequest(request.video, request.video))
    assert sdk.environment is None
