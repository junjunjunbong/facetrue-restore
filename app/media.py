"""Frame-safe local FFmpeg preprocessing. No shell evaluation of uploaded filenames."""

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    frames: int
    duration: float
    has_audio: bool
    field_order: str


def run_ffmpeg(arguments: list[str], ffmpeg: str = "ffmpeg", timeout: int = 300) -> None:
    result = subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-y", *arguments],
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError(f"FFmpeg could not process this video: {result.stderr[-2000:]}")


def probe_video(path: Path, ffprobe: str = "ffprobe", count_frames: bool = False) -> VideoInfo:
    args = [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json"]
    if count_frames:
        args.append("-count_frames")
    result = subprocess.run([*args, str(path)], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise ValueError("Unable to read this video. Upload an ordinary MP4, MOV, AVI, or WebM file.")
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("The file contains no video stream")
    try:
        rate = video.get("avg_frame_rate", "0/1")
        if rate in ("0/0", "0/1"):
            rate = video.get("r_frame_rate", "0/1")
        fps = float(Fraction(rate))
        duration = float(video.get("duration") or data.get("format", {}).get("duration") or 0)
        frames_text = video.get("nb_read_frames") if count_frames else video.get("nb_frames")
        frames = int(frames_text) if str(frames_text).isdigit() else round(duration * fps)
        width, height = int(video["width"]), int(video["height"])
    except (ValueError, ZeroDivisionError, KeyError) as exc:
        raise ValueError("Video metadata is incomplete") from exc
    if min(width, height, fps, frames, duration) <= 0 or width * height > 33_177_600:
        raise ValueError("Unsupported video dimensions, frame rate, or duration")
    return VideoInfo(width, height, fps, frames, duration,
                     any(s.get("codec_type") == "audio" for s in streams), video.get("field_order", "unknown"))


def normalize_video(source: Path, output: Path, width: int, height: int, fps: int,
                    deinterlace: bool = False, max_seconds: float = 10,
                    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> VideoInfo:
    if source.resolve() == output.resolve():
        raise ValueError("Normalization must not overwrite the source")
    info = probe_video(source, ffprobe)
    if info.duration > max_seconds + 0.1:
        raise ValueError(f"This MVP accepts clips up to {max_seconds:g} seconds. Trim the clip first.")
    if width % 32 or height % 32 or min(width, height, fps) <= 0:
        raise ValueError("Use positive fps and model dimensions divisible by 32")
    filters = ["setpts=PTS-STARTPTS"]
    if deinterlace:
        filters += ["bwdif=mode=send_frame:parity=auto:deint=all"]
    filters += [f"fps={fps}", f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black", "setsar=1"]
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", str(source), "-map", "0:v:0", "-map", "0:a:0?", "-vf", ",".join(filters),
                "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-af", "aresample=async=1:first_pts=0", "-ar", "48000",
                "-map_metadata", "-1", "-map_chapters", "-1", "-movflags", "+faststart", str(output)], ffmpeg)
    normalized = probe_video(output, ffprobe, count_frames=True)
    if (normalized.width, normalized.height) != (width, height) or abs(normalized.fps - fps) > 0.01:
        raise ValueError("Normalization produced unexpected dimensions or fps")
    return normalized


def first_frame(video: Path, output: Path, ffmpeg: str = "ffmpeg") -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", str(video), "-frames:v", "1", "-update", "1", str(output)], ffmpeg)
    return output


def mux_original_audio(video: Path, source: Path, output: Path, frames: int, fps: int,
                       ffmpeg: str = "ffmpeg") -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", str(video), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0?",
                "-c:v", "copy", "-c:a", "aac", "-t", f"{frames / fps:.9f}",
                "-map_metadata", "-1", "-movflags", "+faststart", str(output)], ffmpeg)
    return output


PRESETS = {
    "neutral": {"label": "Natural archive", "positive": "Preserve natural textures, clothing and objects from the source.",
                "negative": "modern objects, invented text, plastic skin, face deformation"},
    "vhs_1980s": {"label": "1980s VHS", "positive": "Preserve the original 1980s home-video clothing, hairstyles and objects. Natural faces, gentle texture.",
                  "negative": "smartphones, contemporary cars, LED signage, modern fashion, plastic skin, invented text"},
    "film_1940s": {"label": "1940s home movie", "positive": "Preserve original period clothing, hairstyles, architecture and film character. Natural faces.",
                   "negative": "smartphones, contemporary vehicles, modern signs, LED lights, plastic skin, contemporary fashion"},
}
NEGATIVE_NOTICE = "At the default CFG=1, negative conditioning is skipped. Presets do not guarantee historical accuracy."
