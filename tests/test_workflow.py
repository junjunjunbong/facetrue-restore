"""Offline checks for the graph paths that must remain comparable and local."""

import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app.backends import RestoreRequest
from app.workflow import (
    DISTILLED_SIGMAS, IMAGE_INPUT, LOCAL_NODE_TYPES, OUTPUT_NODE_ID,
    PREVIOUS_NODE_ID, REFERENCE_NODE_ID, VIDEO_INPUT, VIDEO_NODE_ID,
    ModelFiles, build_workflow, validate_graph,
)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.request = RestoreRequest(
            video=Path("/private/client/input.mp4"), output=Path("/private/client/result.mp4"),
            seed=127, width=1280, height=736, frame_count=97, fps=24,
            prompt="A mid-century home movie, natural daylight.",
            negative_prompt="modern phones, compression blocks",
        )
        self.models = ModelFiles()

    def build(self, request=None, **kwargs):
        return build_workflow(request or self.request, "chunk.mp4", model_files=self.models, **kwargs)

    def test_no_photo_has_no_photo_guide_or_loader(self):
        graph = self.build()
        self.assertNotIn(REFERENCE_NODE_ID, graph)
        self.assertNotIn("14", graph)
        self.assertEqual(graph["17"]["inputs"]["latents"], ["12", 2])
        self.assertEqual(sum(n["class_type"] == "LTXAddVideoICLoRAGuide" for n in graph.values()), 1)

    def test_photo_guide_is_outside_video_and_not_streaming(self):
        request = replace(self.request, reference=Path("separate_photo.png"))
        graph = self.build(request, reference_name="reference.png")
        self.assertEqual(graph[REFERENCE_NODE_ID]["inputs"][IMAGE_INPUT], "reference.png")
        photo = graph["14"]["inputs"]
        self.assertEqual(photo["frame_idx"], -1)
        self.assertFalse(photo["use_streaming"])
        self.assertFalse(photo["use_tiled_encode"])
        self.assertEqual(graph["17"]["inputs"]["latents"], ["14", 2])

    def test_chained_photo_graph_preserves_all_three_guides(self):
        request = replace(self.request, reference=Path("photo.png"), previous_frames=Path("prefix.mp4"))
        graph = self.build(request, reference_name="reference.png", previous_name="prefix.mp4")
        self.assertEqual(graph[PREVIOUS_NODE_ID]["inputs"][VIDEO_INPUT], "prefix.mp4")
        self.assertEqual(graph["23"]["class_type"], "LTXVAddGuide")
        self.assertEqual(graph["23"]["inputs"]["frame_idx"], 0)
        self.assertEqual(graph["23"]["inputs"]["latent"], ["12", 2])
        self.assertEqual(graph["14"]["inputs"]["latent"], ["23", 2])
        self.assertEqual(graph["17"]["inputs"]["latents"], ["14", 2])
        validate_graph(graph)

    def test_chained_baseline_uses_its_prefix_without_photo(self):
        request = replace(self.request, previous_frames=Path("baseline_prefix.mp4"))
        graph = self.build(request, previous_name="baseline_prefix.mp4")
        self.assertNotIn(REFERENCE_NODE_ID, graph)
        self.assertEqual(graph["17"]["inputs"]["positive"], ["23", 0])
        self.assertEqual(graph["17"]["inputs"]["negative"], ["23", 1])
        self.assertEqual(graph["17"]["inputs"]["latents"], ["23", 2])

    def test_request_fields_are_injected_without_private_client_paths(self):
        graph = self.build(replace(self.request, frame_count=49, fps=30))
        self.assertEqual(graph[VIDEO_NODE_ID]["inputs"][VIDEO_INPUT], "chunk.mp4")
        self.assertEqual(graph["17"]["inputs"]["seed"], 127)
        self.assertEqual(graph["11"]["inputs"]["length"], 49)
        self.assertEqual(graph["10"]["inputs"]["height"], 736)
        self.assertEqual(graph["11"]["inputs"]["width"], 1280)
        self.assertEqual(graph["7"]["inputs"]["frame_rate"], 30)
        self.assertEqual(graph["19"]["inputs"]["fps"], 30)
        self.assertEqual(graph["5"]["inputs"]["text"], self.request.prompt)
        self.assertEqual(graph["6"]["inputs"]["text"], self.request.negative_prompt)
        self.assertNotIn("/private/client", json.dumps(graph))

    def test_reference_and_baseline_keep_same_seed_and_sampler_settings(self):
        base = self.build()
        photo = self.build(replace(self.request, reference=Path("photo.png")), reference_name="ref.png")
        for key in ("seed", "cfg", "tile_width", "tile_height", "sigmas", "sampler", "tile_frames"):
            self.assertEqual(base["17"]["inputs"][key], photo["17"]["inputs"][key])
        self.assertEqual(base["17"]["inputs"]["tile_width"], 960)
        self.assertEqual(base["17"]["inputs"]["tile_height"], 544)
        self.assertEqual(base["17"]["inputs"]["tile_frames"], 0)
        self.assertEqual(tuple(map(float, base["16"]["inputs"]["sigmas"].split(","))), DISTILLED_SIGMAS)

    def test_invalid_model_dimensions_frames_and_steps_are_rejected(self):
        invalid = [
            {"steps": 4}, {"steps": 12}, {"steps": True}, {"width": 1279}, {"height": 1080},
            {"frame_count": 98}, {"frame_count": 0}, {"frame_count": 240},
            {"seed": -1}, {"seed": 2**32}, {"fps": float("nan")}, {"fps": 0},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(replace(self.request, **changes))

    def test_uploaded_names_must_match_request_assets(self):
        with self.assertRaises(ValueError):
            self.build(reference_name="unrequested.png")
        with self.assertRaises(ValueError):
            self.build(replace(self.request, reference=Path("photo.png")))
        with self.assertRaises(ValueError):
            self.build(replace(self.request, previous_frames=Path("prefix.mp4")))
        with self.assertRaises(ValueError):
            self.build(replace(self.request, previous_frames=Path("prefix.mp4"), frame_count=9), previous_name="prefix.mp4")

    def test_unsafe_uploaded_paths_are_rejected(self):
        for name in ("../private.mp4", "/private.mp4", "https://host/video.mp4", "C:\\private.mp4", "x\x00.mp4"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_workflow(self.request, name, model_files=self.models)
        graph = build_workflow(self.request, "facetrue/chunk.mp4", model_files=self.models)
        self.assertEqual(graph[VIDEO_NODE_ID]["inputs"][VIDEO_INPUT], "facetrue/chunk.mp4")

    def test_graph_is_local_and_uses_low_vram_models(self):
        graph = self.build()
        self.assertTrue(all(node["class_type"] in LOCAL_NODE_TYPES for node in graph.values()))
        self.assertIn("comfy-int8-convrot", graph["1"]["inputs"]["unet_name"])
        self.assertIn("comfy-int8-convrot", graph["2"]["inputs"]["clip_name"])
        self.assertEqual(graph["1"]["inputs"]["weight_dtype"], "default")
        self.assertIn("vae-conv", graph["3"]["inputs"]["vae_name"])
        self.assertEqual(graph[OUTPUT_NODE_ID]["inputs"]["format.codec"], "h264")

    def test_model_overrides_and_builds_are_independent(self):
        with patch.dict("os.environ", {"FACETRUE_TRANSFORMER": "local/custom.safetensors"}):
            models = ModelFiles.from_env()
        graph = build_workflow(self.request, "first.mp4", model_files=models)
        self.assertEqual(graph["1"]["inputs"]["unet_name"], "local/custom.safetensors")
        graph["17"]["inputs"]["seed"] = 999
        self.assertEqual(self.build()["17"]["inputs"]["seed"], 127)

    def test_invalid_graph_is_rejected_before_queueing(self):
        graph = self.build()
        graph["2"]["class_type"] = "GemmaAPITextEncode"
        with self.assertRaises(ValueError):
            validate_graph(graph)
        graph = self.build()
        graph["19"]["inputs"]["images"] = ["missing", 0]
        with self.assertRaises(ValueError):
            validate_graph(graph)
        graph = self.build()
        graph["19"]["inputs"]["images"] = [OUTPUT_NODE_ID, 0]
        with self.assertRaises(ValueError):
            validate_graph(graph)


if __name__ == "__main__":
    unittest.main()
