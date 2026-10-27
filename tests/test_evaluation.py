"""Control-flow tests only; no weights, network, GPU, or invented quality scores."""

import math
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from app.evaluation import (
    CONDITIONS, FaceObservation, FrameScore, _canvas, _validate_experiment, aggregate_scores,
    cosine, require_real_backend, score_observation, validate_clip_sources, verify_model,
)


class EvaluationTests(unittest.TestCase):
    def rows(self):
        return [FrameScore(index, condition, score)
                for index, scores in enumerate(((0.5, 0.8, 0.2), (0.4, 0.6, 0.3)))
                for condition, score in zip(CONDITIONS, scores)]

    def test_paired_improvement_uses_equal_timestamps(self):
        report = aggregate_scores(self.rows())
        self.assertAlmostEqual(report["paired_deltas"]["correct_minus_without"], 0.25)
        self.assertAlmostEqual(report["paired_deltas"]["correct_minus_wrong"], 0.45)
        self.assertEqual(report["common_frame_indices"], [0, 1])
        self.assertEqual(report["status"], "pilot_result")

    def test_missing_detection_excluded_from_all_arms_and_reported(self):
        rows = self.rows()
        rows[-1] = FrameScore(1, "wrong_reference", None, failure_reason="output:no_face")
        report = aggregate_scores(rows, 0.8)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["common_frame_indices"], [0])
        self.assertAlmostEqual(report["paired_deltas"]["correct_minus_without"], 0.3)
        self.assertEqual(report["conditions"][0]["valid_frames"], 2)
        self.assertEqual(report["conditions"][2]["failure_reasons"], {"output:no_face": 1})
        self.assertEqual(report["conditions"][0]["common_coverage"], 0.5)

    def test_no_valid_frames_remains_inconclusive_not_zero_similarity(self):
        report = aggregate_scores([FrameScore(0, c, None, failure_reason="no_face") for c in CONDITIONS])
        self.assertIsNone(report["paired_deltas"]["correct_minus_without"])
        self.assertTrue(all(row["gt_cosine_mean"] is None for row in report["conditions"]))

    def test_unpaired_or_duplicate_rows_rejected(self):
        for rows in (self.rows()[:-1], self.rows() + [self.rows()[0]]):
            with self.assertRaises(ValueError):
                aggregate_scores(rows)

    def test_negative_delta_is_not_hidden(self):
        rows = [FrameScore(0, c, x) for c, x in zip(CONDITIONS, (0.9, 0.5, 0.7))]
        self.assertAlmostEqual(aggregate_scores(rows)["paired_deltas"]["correct_minus_without"], -0.4)

    def test_invalid_scores_and_embeddings_rejected(self):
        for values in (((), ()), ((0., 0.), (1., 1.)), ((math.nan,), (1.,)), ((1.,), (1., 0.))):
            with self.assertRaises(ValueError):
                cosine(*values)
        with self.assertRaises(ValueError):
            aggregate_scores([FrameScore(0, c, math.nan) for c in CONDITIONS])

    def test_metric_uses_clean_target_not_reference_only(self):
        clean, restored = FaceObservation((1., 0.)), FaceObservation((0., 1.))
        row = score_observation(0, "correct_reference", clean, restored, restored, clean)
        self.assertEqual(row.gt_cosine, 0.)
        self.assertEqual(row.correct_photo_cosine, 1.)

    def test_ground_truth_failure_retained(self):
        valid = FaceObservation((1., 0.))
        row = score_observation(0, CONDITIONS[0], FaceObservation(reason="ambiguous_faces:2"), valid, valid, valid)
        self.assertIsNone(row.gt_cosine)
        self.assertEqual(row.failure_reason, "ground_truth:ambiguous_faces:2")

    def test_mock_backends_cannot_create_evidence(self):
        class MockBackend:
            pass
        class RealBackend:
            pass
        with self.assertRaises(ValueError):
            require_real_backend(MockBackend(), "comfy")
        with self.assertRaises(ValueError):
            require_real_backend(RealBackend(), "mock")
        require_real_backend(RealBackend(), "comfy")

    def make_clip(self, root):
        for name, content in (("hq.mp4", b"hq"), ("correct.png", b"correct"), ("wrong.png", b"wrong")):
            (root / name).write_bytes(content)
        return {"hq_video": "hq.mp4", "reference": "correct.png", "wrong_reference": "wrong.png",
                "independent_reference_confirmed": True, "reference_origin": "Separate still camera capture",
                "source_rights": "Creator's own consenting footage", "identity_id": "a", "wrong_identity_id": "b",
                "face_bbox": {"x": 10, "y": 10, "width": 20, "height": 20}}

    def test_same_reference_bytes_and_missing_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = self.make_clip(root)
            validate_clip_sources(clip, root)
            clip["independent_reference_confirmed"] = False
            with self.assertRaises(ValueError):
                validate_clip_sources(clip, root)
            clip["independent_reference_confirmed"] = True
            (root / "wrong.png").write_bytes((root / "correct.png").read_bytes())
            with self.assertRaises(ValueError):
                validate_clip_sources(clip, root)

    def test_wrong_photo_must_claim_different_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = self.make_clip(root)
            clip["wrong_identity_id"] = clip["identity_id"]
            with self.assertRaises(ValueError):
                validate_clip_sources(clip, root)

    def test_bad_or_missing_weight_rejected_without_download(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.onnx"
            with self.assertRaises(FileNotFoundError):
                verify_model(path, "sface")
            path.write_bytes(b"version https://git-lfs.github.com/spec/v1")
            with self.assertRaises(ValueError):
                verify_model(path, "sface")

    def test_experiment_dimensions_and_ids_are_validated(self):
        cfg = _validate_experiment({"version": 1, "clips": [{"id": "pilot-1"}]})
        self.assertEqual(cfg["frame_count"], 97)
        for bad in ({"width": 127}, {"frame_count": 10000}, {"sample_every": 0}, {"fps": 24.5}, {"steps": 12},
                    {"clips": [{"id": "../private"}]}, {"clips": [{"id": "a"}, {"id": "a"}]}):
            with self.assertRaises(ValueError):
                _validate_experiment({"version": 1, "clips": [{"id": "a"}], **bad})

    def test_canvas_adapter_uses_integer_boxes_and_clamps_auto_detection(self):
        captured = {}
        class IntegerBBox:
            def __init__(self, **values):
                if not all(isinstance(value, int) for value in values.values()):
                    raise ValueError("BBox requires integer pixels")
                self.values = values
        def builder(photo, output, bbox, width, height, photo_bbox=None):
            captured.update(target=bbox.values, photo=photo_bbox.values)
            output.write_bytes(b"control-flow fixture")
        module = types.ModuleType("app.reference")
        module.BBox = IntegerBBox
        module.build_reference_canvas = builder
        module.read_photo = lambda path: types.SimpleNamespace(size=(50, 50))
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", {"app.reference": module}):
            root = Path(directory)
            _canvas(root / "photo.jpg", root / "canvas.png",
                    FaceObservation((1.,), (-0.2, 2.4, 20.8, 30.5)),
                    {"face_bbox": {"x": 10, "y": 20, "width": 30, "height": 40}},
                    "reference", 128, 128)
            self.assertEqual(captured["photo"], {"x": 0, "y": 2, "width": 21, "height": 31})
            self.assertEqual(captured["target"], {"x": 10, "y": 20, "width": 30, "height": 40})


if __name__ == "__main__":
    unittest.main()
