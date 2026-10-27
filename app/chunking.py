"""Frame-indexed 97/17 windows with explicit tail padding and overlap removal."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TypeVar

T = TypeVar("T")
WINDOW = 97
OVERLAP = 17
STRIDE = WINDOW - OVERLAP


@dataclass(frozen=True)
class Chunk:
    index: int
    start: int
    valid_frames: int
    model_frames: int
    overlap: int

    @property
    def end(self) -> int:
        return self.start + self.valid_frames

    @property
    def padding(self) -> int:
        return self.model_frames - self.valid_frames


def plan_chunks(total_frames: int) -> list[Chunk]:
    if isinstance(total_frames, bool) or not isinstance(total_frames, int) or total_frames < 1:
        raise ValueError("total_frames must be a positive integer")
    chunks = []
    start = 0
    while True:
        valid = min(WINDOW, total_frames - start)
        padded = ((valid - 1 + 7) // 8) * 8 + 1
        chunks.append(Chunk(len(chunks), start, valid, padded, OVERLAP if start else 0))
        if start + valid == total_frames:
            return chunks
        start += STRIDE


def stitch_sequences(chunks: Sequence[Sequence[T]], plan: Sequence[Chunk], expected_frames: int) -> list[T]:
    """Keep earlier restored overlap. Later chunks must be conditioned on those frames."""
    if len(chunks) != len(plan) or list(plan) != plan_chunks(expected_frames):
        raise ValueError("Chunk plan does not match expected video length")
    result: list[T] = []
    for values, chunk in zip(chunks, plan, strict=True):
        if len(values) != chunk.model_frames:
            raise ValueError(f"Chunk {chunk.index}: expected {chunk.model_frames} generated frames, got {len(values)}")
        result.extend(values[chunk.overlap:chunk.valid_frames])
    if len(result) != expected_frames:
        raise ValueError(f"Stitched count {len(result)} != expected {expected_frames}")
    return result


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-3000:]}")


def extract_chunk(source: Path, output: Path, chunk: Chunk, fps: int, ffmpeg: str = "ffmpeg") -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    filters = f"trim=start_frame={chunk.start}:end_frame={chunk.end},setpts=PTS-STARTPTS"
    if chunk.padding:
        filters += f",tpad=stop_mode=clone:stop={chunk.padding}"
    _run([ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(source), "-an", "-vf", filters,
          "-frames:v", str(chunk.model_frames), "-r", str(fps), "-c:v", "libx264", "-crf", "18",
          "-pix_fmt", "yuv420p", str(output)])
    return output


def extract_previous_tail(restored: Path, output: Path, model_frames: int, fps: int,
                          ffmpeg: str = "ffmpeg") -> Path:
    if model_frames < OVERLAP:
        raise ValueError("Previous chunk is shorter than the overlap")
    tail = Chunk(0, model_frames - OVERLAP, OVERLAP, OVERLAP, 0)
    return extract_chunk(restored, output, tail, fps, ffmpeg)


def stitch_videos(videos: Sequence[Path], plan: Sequence[Chunk], output: Path,
                   expected_frames: int, fps: int, ffmpeg: str = "ffmpeg") -> Path:
    """Trim padding and duplicate frames by index, then encode one continuous H.264 stream."""
    if len(videos) != len(plan) or list(plan) != plan_chunks(expected_frames):
        raise ValueError("Videos and plan do not match the expected length")
    command = [ffmpeg, "-nostdin", "-v", "error", "-y"]
    for path in videos:
        command += ["-i", str(path)]
    filters = []
    for i, chunk in enumerate(plan):
        filters.append(f"[{i}:v]trim=start_frame={chunk.overlap}:end_frame={chunk.valid_frames},setpts=PTS-STARTPTS[v{i}]")
    inputs = "".join(f"[v{i}]" for i in range(len(plan)))
    filters.append(f"{inputs}concat=n={len(plan)}:v=1:a=0[out]")
    output.parent.mkdir(parents=True, exist_ok=True)
    command += ["-filter_complex", ";".join(filters), "-map", "[out]", "-an", "-r", str(fps),
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    _run(command)
    actual = count_video_frames(output)
    if actual != expected_frames:
        output.unlink(missing_ok=True)
        raise ValueError(f"Stitch produced {actual} frames; expected {expected_frames}")
    return output


def count_video_frames(video: Path, ffprobe: str = "ffprobe") -> int:
    import json

    result = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
                             "-show_entries", "stream=nb_read_frames", "-of", "json", str(video)],
                            capture_output=True, text=True, timeout=300, check=True)
    streams = json.loads(result.stdout).get("streams", [])
    if not streams or not str(streams[0].get("nb_read_frames", "")).isdigit():
        raise ValueError("Unable to count decoded frames")
    return int(streams[0]["nb_read_frames"])
