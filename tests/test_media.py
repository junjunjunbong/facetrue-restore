import shutil
import subprocess

import pytest

from app.media import first_frame, normalize_video, probe_video

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")


def make_video(path, duration=1, audio=False):
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x96:rate=12"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=400:sample_rate=48000"]
    subprocess.run([*cmd, "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


@pytest.mark.parametrize("deinterlace", [False, True])
def test_normalize_fps_dimensions_and_audio(tmp_path, deinterlace):
    source = tmp_path / "source with spaces.mp4"
    make_video(source, audio=True)
    output = tmp_path / "normal.mp4"
    info = normalize_video(source, output, 128, 96, 24, deinterlace)
    assert (info.width, info.height, info.fps, info.frames) == (128, 96, 24, 24)
    assert info.has_audio
    assert source.is_file()
    assert first_frame(output, tmp_path / "first.png").is_file()


def test_long_clip_is_rejected_not_silently_truncated(tmp_path):
    source = tmp_path / "long.mp4"
    make_video(source, duration=1)
    with pytest.raises(ValueError, match="Trim"):
        normalize_video(source, tmp_path / "out.mp4", 128, 96, 24, max_seconds=0.5)


def test_non_video_has_clear_error(tmp_path):
    source = tmp_path / "bad.mp4"
    source.write_bytes(b"not video")
    with pytest.raises(ValueError, match="Unable to read"):
        probe_video(source)
