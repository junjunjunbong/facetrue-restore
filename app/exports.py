"""Synchronized comparison exports with bounded-memory RGB frame streaming.

Pillow's bundled font draws labels. FFmpeg drawtext and system fonts are not
required. No input is truncated to accommodate a shorter restoration result.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.media import mux_original_audio, probe_video


HEADER = 80
FOOTER = 48
MOCK_NOTICE = "MOCK - INPUT COPY, NO AI RESTORATION"
SYNTHETIC_NOTICE = "SYNTHETICALLY DEGRADED TEST CLIP"


def _font(text: str, max_width: int, size: int = 24):
    for value in range(size, 0, -1):
        font = ImageFont.load_default(size=value)
        if font.getlength(text) <= max_width:
            return font
    return ImageFont.load_default(size=1)


def _center_text(image: Image.Image, text: str, box: tuple[int, int, int, int],
                 size: int = 24, color: str = "#f6f3eb") -> None:
    draw = ImageDraw.Draw(image)
    x, y, width, height = box
    font = _font(text, max(1, width - 12), size)
    bounds = draw.textbbox((0, 0), text, font=font)
    draw.text((x + (width - (bounds[2] - bounds[0])) / 2 - bounds[0],
               y + (height - (bounds[3] - bounds[1])) / 2 - bounds[1]),
              text, font=font, fill=color)


def _template(width: int, body_height: int, *, panels: int, mock: bool, synthetic: bool) -> Image.Image:
    image = Image.new("RGB", (width, HEADER + body_height + FOOTER), "#111827")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, HEADER - 2, width, HEADER - 1), fill="#414c60")
    if panels == 3:
        for i, label in enumerate(("Original", "Without photo", "With photo")):
            _center_text(image, label, (i * (width // 3), 0, width // 3, HEADER), size=26)
    else:
        _center_text(image, "Without photo", (0, 0, width // 2, HEADER), size=26)
        _center_text(image, "With photo", (width // 2, 0, width - width // 2, HEADER), size=26)
    footer_y = HEADER + body_height
    footer_color = "#912b39" if mock else "#695018" if synthetic else "#111827"
    draw.rectangle((0, footer_y, width, image.height), fill=footer_color)
    notices = []
    if mock:
        notices.append(MOCK_NOTICE)
    if synthetic:
        notices.append(SYNTHETIC_NOTICE)
    if not notices:
        notices = ["Synchronized frames"]
    line_height = FOOTER // len(notices)
    for i, notice in enumerate(notices):
        _center_text(image, notice, (0, footer_y + i * line_height, width, line_height),
                     size=28 if len(notices) == 1 else 19)
    return image


class _Process:
    def __init__(self, args: list[str], *, reader: bool):
        self.error_log = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(args, stdin=subprocess.DEVNULL if reader else subprocess.PIPE,
                                            stdout=subprocess.PIPE if reader else subprocess.DEVNULL,
                                            stderr=self.error_log)
        except Exception:
            self.error_log.close()
            raise
        self.reader = reader

    def __enter__(self):
        return self

    def _error(self) -> str:
        self.error_log.seek(0)
        return self.error_log.read().decode("utf-8", errors="replace")[-3000:]

    def read(self, size: int) -> bytes:
        return self.process.stdout.read(size)

    def write(self, frame: np.ndarray) -> None:
        try:
            self.process.stdin.write(frame.tobytes())
        except (BrokenPipeError, OSError) as error:
            raise ValueError(f"FFmpeg comparison encoder stopped: {self._error()}") from error

    def finish(self) -> None:
        if self.reader:
            if self.read(1):
                raise ValueError("Input has extra decoded frames; refusing to truncate")
            self.process.stdout.close()
        else:
            try:
                self.process.stdin.close()
            except BrokenPipeError as error:
                raise ValueError(f"FFmpeg encoder stopped: {self._error()}") from error
        try:
            code = self.process.wait(timeout=180)
        except subprocess.TimeoutExpired as error:
            raise ValueError("FFmpeg export did not finish within 180 seconds") from error
        if code:
            raise ValueError(f"FFmpeg export failed: {self._error()}")

    def __exit__(self, kind, value, traceback):
        # Terminate before closing a blocked encoder pipe on exception.
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout):
            if stream and not stream.closed:
                try:
                    stream.close()
                except BrokenPipeError:
                    pass
        self.error_log.close()


def _decoder(path: Path, ffmpeg: str) -> _Process:
    return _Process([ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-threads", "1",
                     "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn", "-vsync", "0",
                     "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", "1", "pipe:1"], reader=True)


def _encoder(path: Path, width: int, height: int, fps: int, ffmpeg: str) -> _Process:
    return _Process([ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-y",
                     "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", f"{width}x{height}",
                     "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264", "-crf", "18",
                     "-preset", "fast", "-threads", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                     str(path)], reader=False)


def _read_frame(reader: _Process, width: int, height: int, index: int) -> Image.Image:
    expected = width * height * 3
    payload = reader.read(expected)
    if len(payload) != expected:
        raise ValueError(f"Input decode ended at frame {index}; expected a complete synchronized frame")
    return Image.frombytes("RGB", (width, height), payload)


def _dimensions(width: int, height: int, cap: int) -> tuple[int, int]:
    scaled_width = max(2, min(width, cap) // 2 * 2)
    scaled_height = max(2, round(height * scaled_width / width / 2) * 2)
    return scaled_width, scaled_height


def _check_inputs(paths: tuple[Path, ...], fps: int, expected_frames: int, ffprobe: str):
    if not isinstance(fps, int) or fps <= 0 or not isinstance(expected_frames, int) or expected_frames <= 0:
        raise ValueError("fps and expected_frames must be positive integers")
    infos = [probe_video(Path(path), ffprobe, count_frames=True) for path in paths]
    size = (infos[0].width, infos[0].height)
    for path, info in zip(paths, infos):
        if info.frames != expected_frames:
            raise ValueError(f"Frame count mismatch for {path.name}: {info.frames} vs {expected_frames}")
        if abs(info.fps - fps) > 0.01:
            raise ValueError(f"FPS mismatch for {path.name}: {info.fps} vs {fps}")
        if (info.width, info.height) != size:
            raise ValueError(f"Dimensions mismatch for {path.name}")
    return infos


def _verify_export(path: Path, width: int, height: int, fps: int, frames: int,
                   audio: bool, ffprobe: str) -> None:
    info = probe_video(path, ffprobe, count_frames=True)
    if ((info.width, info.height, info.frames) != (width, height, frames)
            or abs(info.fps - fps) > 0.01 or info.has_audio != audio):
        raise ValueError("Comparison export failed frame, dimensions, fps, or audio validation")


def export_comparisons(original: Path, without: Path, with_reference: Path, output_dir: Path,
                       fps: int, expected_frames: int, mock: bool = False, synthetic: bool = False,
                       ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Path]:
    paths = tuple(Path(path).resolve() for path in (original, without, with_reference))
    infos = _check_inputs(paths, fps, expected_frames, ffprobe)
    width, height = infos[0].width, infos[0].height
    panel_w, panel_h = _dimensions(width, height, 640)
    wipe_w, wipe_h = _dimensions(width, height, 1280)
    side_size = (3 * panel_w, HEADER + panel_h + FOOTER)
    wipe_size = (wipe_w, HEADER + wipe_h + FOOTER)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {"side_by_side": output_dir / "comparison-side-by-side.mp4",
               "wipe": output_dir / "comparison-wipe.mp4"}
    for output in outputs.values():
        if output in paths or output.exists():
            raise FileExistsError(f"Refusing to overwrite an existing file: {output}")
    templates = {"side_by_side": _template(side_size[0], panel_h, panels=3, mock=mock, synthetic=synthetic),
                 "wipe": _template(wipe_w, wipe_h, panels=2, mock=mock, synthetic=synthetic)}
    with tempfile.TemporaryDirectory(prefix=".comparison-", dir=output_dir) as temporary:
        scratch = Path(temporary)
        silent = {key: scratch / f"{key}-silent.mp4" for key in outputs}
        with ExitStack() as stack:
            readers = [stack.enter_context(_decoder(path, ffmpeg)) for path in paths]
            writers = {"side_by_side": stack.enter_context(_encoder(silent["side_by_side"], *side_size, fps, ffmpeg)),
                       "wipe": stack.enter_context(_encoder(silent["wipe"], *wipe_size, fps, ffmpeg))}
            for index in range(expected_frames):
                frames = [_read_frame(reader, width, height, index) for reader in readers]
                side = templates["side_by_side"].copy()
                for panel, frame in enumerate(frames):
                    side.paste(frame.resize((panel_w, panel_h), Image.Resampling.LANCZOS), (panel * panel_w, HEADER))
                writers["side_by_side"].write(np.asarray(side))
                left = frames[1].resize((wipe_w, wipe_h), Image.Resampling.LANCZOS)
                right = frames[2].resize((wipe_w, wipe_h), Image.Resampling.LANCZOS)
                cut = round(wipe_w * index / (expected_frames - 1)) if expected_frames > 1 else wipe_w // 2
                body = right.copy()
                if cut:
                    body.paste(left.crop((0, 0, cut, wipe_h)), (0, 0))
                if 0 < cut < wipe_w:
                    ImageDraw.Draw(body).line((cut, 0, cut, wipe_h), fill="#fde68a", width=2)
                wipe = templates["wipe"].copy()
                wipe.paste(body, (0, HEADER))
                writers["wipe"].write(np.asarray(wipe))
            for reader in readers:
                reader.finish()
            for writer in writers.values():
                writer.finish()
        prepared = {}
        for key, size in (("side_by_side", side_size), ("wipe", wipe_size)):
            prepared[key] = scratch / f"{key}-audio.mp4"
            mux_original_audio(silent[key], paths[0], prepared[key], expected_frames, fps, ffmpeg)
            _verify_export(prepared[key], *size, fps, expected_frames, infos[0].has_audio, ffprobe)
        for key, path in prepared.items():
            path.replace(outputs[key])
    return outputs


def label_mock_video(source: Path, output: Path, fps: int, expected_frames: int,
                     ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> Path:
    """Burn a conspicuous mock label into a standalone arm without changing size."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or output.exists():
        raise FileExistsError("Mock labeling must not overwrite source or an existing output")
    info = _check_inputs((source,), fps, expected_frames, ffprobe)[0]
    if info.width % 2 or info.height % 2:
        raise ValueError("Mock export expects normalized even dimensions")
    output.parent.mkdir(parents=True, exist_ok=True)
    banner_height = min(info.height, max(24, min(64, round(info.height / 8))))
    banner = Image.new("RGB", (info.width, banner_height), "#912b39")
    _center_text(banner, MOCK_NOTICE, (0, 0, info.width, banner_height), size=32)
    with tempfile.TemporaryDirectory(prefix=".mock-label-", dir=output.parent) as temporary:
        silent, final = Path(temporary) / "silent.mp4", Path(temporary) / "audio.mp4"
        with _decoder(source, ffmpeg) as reader, _encoder(silent, info.width, info.height, fps, ffmpeg) as writer:
            for index in range(expected_frames):
                frame = _read_frame(reader, info.width, info.height, index)
                frame.paste(banner, (0, info.height - banner_height))
                writer.write(np.asarray(frame))
            reader.finish()
            writer.finish()
        mux_original_audio(silent, source, final, expected_frames, fps, ffmpeg)
        _verify_export(final, info.width, info.height, fps, expected_frames, info.has_audio, ffprobe)
        final.replace(output)
    return output
