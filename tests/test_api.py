import io
import json
import shutil
import subprocess
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")


@pytest.fixture
def sample_video(tmp_path):
    path = tmp_path / "sample.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=128x128:rate=24", "-t", "4", "-c:v", "libx264", str(path)], check=True)
    return path


def settings(tmp_path):
    return Settings(_env_file=None, mode="mock", width=128, height=128, data_dir=tmp_path / "data")


def upload_fixture(client, sample_video):
    with sample_video.open("rb") as video:
        response = client.post("/api/uploads", files={"video": ("test.mp4", video, "video/mp4")},
                               data={"deinterlace": "true"})
    assert response.status_code == 200, response.text
    uploaded = response.json()
    photo = io.BytesIO()
    Image.new("RGB", (80, 80), (220, 80, 80)).save(photo, format="PNG")
    result = client.post(f"/api/uploads/{uploaded['upload_id']}/photo",
                         files={"photo": ("portrait.png", photo.getvalue(), "image/png")})
    assert result.status_code == 200, result.text
    return uploaded, result.json()


def test_upload_canvas_job_download(tmp_path, sample_video):
    with TestClient(create_app(settings(tmp_path))) as client:
        uploaded, photo = upload_fixture(client, sample_video)
        assert uploaded["frame_count"] == 96
        assert client.get(uploaded["frame_url"]).headers["content-type"] == "image/png"
        response = client.post("/api/canvas", json={
            "upload_id": uploaded["upload_id"], "photo_id": photo["photo_id"],
            "bbox": {"x": 20, "y": 20, "width": 40, "height": 40},
            "photo_bbox": {"x": 0, "y": 0, "width": 80, "height": 80},
        })
        assert response.status_code == 200, response.text
        canvas = response.json()
        assert canvas["frame_idx"] == -1
        result = client.post("/api/jobs", json={"upload_id": uploaded["upload_id"],
            "reference_id": canvas["reference_id"], "seed": 1, "preset": "vhs_1980s", "synthetic": True})
        assert result.status_code == 202, result.text
        job_id = result.json()["id"]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.1)
        assert job["status"] == "succeeded", job
        assert job["mode"] == "mock"
        assert set(job["outputs"]) >= {"original", "without", "with", "side_by_side", "wipe", "manifest"}
        result = client.get(job["outputs"]["side_by_side"], headers={"Range": "bytes=0-31"})
        assert result.status_code == 206 and len(result.content) == 32
        manifest = client.get(job["outputs"]["manifest"]).json()
        assert manifest["mock"] and manifest["synthetically_degraded"]
        assert not manifest["quality_evidence"]


def test_invalid_bbox_and_paths_are_rejected(tmp_path, sample_video):
    with TestClient(create_app(settings(tmp_path))) as client:
        uploaded, photo = upload_fixture(client, sample_video)
        result = client.post("/api/canvas", json={"upload_id": uploaded["upload_id"], "photo_id": photo["photo_id"],
            "bbox": {"x": 120, "y": 0, "width": 40, "height": 40}})
        assert result.status_code == 422
        assert client.get(f"/api/media/{uploaded['upload_id']}/meta.json").status_code == 404
        assert client.get("/api/jobs/not-a-job").status_code == 404
        assert client.post("/api/uploads", files={"video": ("x.html", b"hello")}).status_code == 415


def test_restart_marks_interrupted_job_failed(tmp_path):
    config = settings(tmp_path)
    job_dir = config.data_dir / "jobs" / ("a" * 32)
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps({"id": "a" * 32, "status": "running"}))
    with TestClient(create_app(config)) as client:
        job = client.get("/api/jobs/" + "a" * 32).json()
        assert job["status"] == "failed" and "restarted" in job["error"]


def test_upload_limit(tmp_path):
    config = settings(tmp_path).model_copy(update={"upload_limit_mb": 1})
    with TestClient(create_app(config)) as client:
        result = client.post("/api/uploads", files={"video": ("huge.mp4", b"x" * (1024**2 + 1))})
        assert result.status_code == 413
