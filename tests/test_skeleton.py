from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.backends import MockBackend, RestoreRequest
from app.config import Settings
from app.main import create_app


def test_mock_app_is_offline_and_explicit(tmp_path):
    settings = Settings(_env_file=None, mode="mock", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/health").json()["gpu_checked"] is False
        config = client.get("/api/config").json()
        assert config["mode"] == "mock"
        assert "No AI restoration" in config["mock_notice"]
    assert (tmp_path / "uploads").is_dir()


def test_invalid_mode_and_dimensions_fail():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode="cloud")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, width=1279)


async def test_mock_copies_without_inventing_photo_effect(tmp_path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"synthetic-test-data")
    backend = MockBackend()
    outputs = []
    for name, reference in (("without", None), ("with", Path("unused-photo.png"))):
        result = await backend.restore(RestoreRequest(source, tmp_path / f"{name}.mp4", reference=reference))
        outputs.append(result.read_bytes())
    assert outputs == [source.read_bytes(), source.read_bytes()]


async def test_mock_rejects_overwrite(tmp_path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"test")
    with pytest.raises(ValueError):
        await MockBackend().restore(RestoreRequest(source, source))
