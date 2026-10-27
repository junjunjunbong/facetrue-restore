"""Actual FFmpeg fixtures exercise synchronization, audio and burned notices."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy as np

from app.exports import export_comparisons, label_mock_video
from app.media import probe_video


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe required")
class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def clip(self, name, color, *, frames=4, fps=4, width=64, height=48, audio=False):
        path = self.root / name
        args = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
                "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:r={fps}"]
        if audio:
            args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-c:a", "aac"]
        args += ["-frames:v", str(frames), "-t", str(frames / fps), "-c:v", "libx264", "-threads", "1",
                 "-pix_fmt", "yuv420p", str(path)]
        subprocess.run(args, check=True, capture_output=True, timeout=30)
        return path

    def decode(self, path):
        info = probe_video(path)
        result = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-i", str(path),
                                 "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", "1", "pipe:1"],
                                capture_output=True, check=True, timeout=30)
        return np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, info.height, info.width, 3)

    def test_same_frames_panels_wipe_and_original_audio(self):
        original = self.clip("original.mp4", "red", audio=True)
        without = self.clip("without.mp4", "blue")
        with_photo = self.clip("with.mp4", "lime")
        result = export_comparisons(original, without, with_photo, self.root / "exports", 4, 4)
        info = probe_video(result["side_by_side"], count_frames=True)
        self.assertEqual((info.width, info.height, info.frames, info.fps), (192, 176, 4, 4.0))
        self.assertTrue(info.has_audio)
        panels = self.decode(result["side_by_side"])
        self.assertGreater(int(panels[0, 104, 32, 0]), 200)
        self.assertGreater(int(panels[0, 104, 96, 2]), 200)
        self.assertGreater(int(panels[0, 104, 160, 1]), 200)
        wipe = self.decode(result["wipe"])
        self.assertEqual(wipe.shape, (4, 176, 64, 3))
        self.assertGreater(int(wipe[0, 104, 16, 1]), 200)
        self.assertGreater(int(wipe[-1, 104, 16, 2]), 200)
        self.assertTrue(probe_video(result["wipe"], count_frames=True).has_audio)

    def test_mock_and_synthetic_notices_burned_into_export(self):
        source = self.clip("source.mp4", "black", width=320, height=180)
        outputs = export_comparisons(source, source, source, self.root / "notices", 4, 4, mock=True, synthetic=True)
        decoded = self.decode(outputs["side_by_side"])
        footer = decoded[0, -48:]
        self.assertGreater(int(footer[2, 2, 0]), int(footer[2, 2, 1]) + 50)
        bright = (footer[:, :, :3] > 185).all(axis=2)
        self.assertGreater(int(bright[:24].sum()), 50)
        self.assertGreater(int(bright[24:].sum()), 50)
        self.assertFalse(probe_video(outputs["wipe"]).has_audio)

    def test_frame_order_stays_synchronized_across_three_arms(self):
        sequences = [((220, 20, 20), (20, 220, 20), (20, 20, 220), (180, 180, 20)),
                     ((20, 20, 210), (210, 20, 20), (20, 210, 20), (20, 180, 180)),
                     ((70, 70, 70), (110, 110, 110), (160, 160, 160), (210, 210, 210))]
        paths = []
        for arm, colors in enumerate(sequences):
            path = self.root / f"sequence-{arm}.mp4"
            pixels = np.stack([np.full((48, 64, 3), color, dtype=np.uint8) for color in colors])
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", "64x48", "-r", "4", "-i", "pipe:0",
                            "-an", "-c:v", "libx264", "-crf", "10", "-threads", "1", "-pix_fmt", "yuv420p", str(path)],
                           input=pixels.tobytes(), check=True, capture_output=True, timeout=30)
            paths.append(path)
        outputs = export_comparisons(*paths, self.root / "sequences", 4, 4)
        panels = self.decode(outputs["side_by_side"])
        for index in range(4):
            for arm in range(3):
                actual = panels[index, 104, 32 + 64 * arm].astype(int)
                expected = np.asarray(sequences[arm][index])
                self.assertLess(int(np.abs(actual - expected).max()), 15)

    def test_standalone_mock_video_keeps_dimensions_frames_audio(self):
        source = self.clip("source.mp4", "black", width=320, height=180, audio=True)
        target = label_mock_video(source, self.root / "mock.mp4", 4, 4)
        info = probe_video(target, count_frames=True)
        self.assertEqual((info.width, info.height, info.frames), (320, 180, 4))
        self.assertTrue(info.has_audio)
        pixels = self.decode(target)[0]
        self.assertGreater(int(pixels[-2, 2, 0]), int(pixels[-2, 2, 1]) + 50)
        self.assertGreater(int((pixels[-24:] > 185).all(axis=2).sum()), 10)

    def test_mismatched_frames_dimensions_and_fps_fail(self):
        original = self.clip("normal.mp4", "red")
        variants = [self.clip("short.mp4", "blue", frames=3),
                    self.clip("size.mp4", "blue", width=80),
                    self.clip("rate.mp4", "blue", fps=8)]
        for index, variant in enumerate(variants):
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, "mismatch"):
                export_comparisons(original, original, variant, self.root / f"bad-{index}", 4, 4)
            self.assertFalse((self.root / f"bad-{index}" / "comparison-side-by-side.mp4").exists())

    def test_existing_output_is_preserved(self):
        original = self.clip("source.mp4", "red")
        directory = self.root / "exports"
        directory.mkdir()
        target = directory / "comparison-side-by-side.mp4"
        target.write_bytes(b"previous evidence")
        with self.assertRaises(FileExistsError):
            export_comparisons(original, original, original, directory, 4, 4)
        self.assertEqual(target.read_bytes(), b"previous evidence")


if __name__ == "__main__":
    unittest.main()
