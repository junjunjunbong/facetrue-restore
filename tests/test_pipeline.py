import shutil
import subprocess

import pytest
from PIL import Image

from app.backends import MockBackend
from app.config import Settings
from app.media import probe_video
from app.pipeline import restore_video, run_comparison

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")


class RecordingBackend(MockBackend):
    def __init__(self):
        self.requests = []

    async def restore(self, request):
        self.requests.append(request)
        return await super().restore(request)


async def test_paired_chain_uses_same_seeds_separate_histories(tmp_path):
    source = tmp_path / "input.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=128x128:rate=24", "-frames:v", "98", "-c:v", "libx264", str(source)], check=True)
    photo = tmp_path / "ref.png"
    Image.new("RGB", (128, 128), (128, 128, 128)).save(photo)
    settings = Settings(_env_file=None, width=128, height=128, mode="mock", data_dir=tmp_path)
    backend = RecordingBackend()
    result = await run_comparison(source, photo, tmp_path / "out", backend, settings, seed=2026, synthetic=True)
    assert [r.seed for r in backend.requests] == [2026, 2027, 2026, 2027]
    assert [r.frame_count for r in backend.requests] == [97, 25, 97, 25]
    assert [r.reference is None for r in backend.requests] == [True, True, False, False]
    prefixes = [r.previous_frames for r in backend.requests if r.previous_frames]
    assert len(prefixes) == 2 and prefixes[0] != prefixes[1]
    assert all(probe_video(p, count_frames=True).frames == 17 for p in prefixes)
    assert all(probe_video(result[key], count_frames=True).frames == 98
               for key in ("original", "without", "with", "side_by_side", "wipe"))
    assert '"mock": true' in result["manifest"].read_text()


async def test_invalid_canvas_fails_before_inference(tmp_path):
    source = tmp_path / "input.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=size=128x128:rate=24", "-frames:v", "49", "-c:v", "libx264", str(source)], check=True)
    photo = tmp_path / "wrong.png"
    Image.new("RGB", (64, 64)).save(photo)
    backend = RecordingBackend()
    settings = Settings(_env_file=None, width=128, height=128, data_dir=tmp_path)
    with pytest.raises(ValueError, match="canvas"):
        await restore_video(source, photo, tmp_path / "out.mp4", backend, settings)
    assert not backend.requests


async def test_existing_comparison_is_never_overwritten(tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    sentinel = output / "original.mp4"
    sentinel.write_bytes(b"old result")
    config = Settings(_env_file=None, data_dir=tmp_path)
    with pytest.raises(FileExistsError):
        await run_comparison(tmp_path / "missing.mp4", tmp_path / "missing.png", output, MockBackend(), config)
    assert sentinel.read_bytes() == b"old result"
