import shutil
import subprocess

import pytest

from app.chunking import count_video_frames, extract_chunk, plan_chunks, stitch_sequences, stitch_videos


@pytest.mark.parametrize("count", [1, 8, 9, 17, 49, 96, 97, 98, 113, 177, 178, 240, 300, 600])
def test_each_source_frame_survives_once(count):
    plan = plan_chunks(count)
    parts = []
    for chunk in plan:
        frames = list(range(chunk.start, chunk.end))
        parts.append(frames + [frames[-1]] * chunk.padding)
        assert chunk.model_frames % 8 == 1
        assert chunk.model_frames <= 97
    assert stitch_sequences(parts, plan, count) == list(range(count))


def test_ten_seconds_at_24fps():
    plan = plan_chunks(240)
    assert [c.start for c in plan] == [0, 80, 160]
    assert [c.valid_frames for c in plan] == [97, 97, 80]
    assert [c.model_frames for c in plan] == [97, 97, 81]


def test_missing_output_frames_rejected():
    with pytest.raises(ValueError, match="generated frames"):
        stitch_sequences([list(range(96))], plan_chunks(97), 97)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_encoded_join_has_exact_length(tmp_path):
    source = tmp_path / "input.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=128x96:rate=24", "-frames:v", "178", "-c:v", "libx264", str(source)], check=True)
    plan = plan_chunks(178)
    chunks = [extract_chunk(source, tmp_path / f"chunk-{c.index}.mp4", c, 24) for c in plan]
    assert [count_video_frames(p) for p in chunks] == [97, 97, 25]
    output = stitch_videos(chunks, plan, tmp_path / "joined.mp4", 178, 24)
    assert count_video_frames(output) == 178
