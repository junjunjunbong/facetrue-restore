"""Build a local-only LTX Restore API graph from the official tiled workflow.

The caller uploads assets first. This module only uses their ComfyUI input names;
it never sends an absolute client path to the GPU server. See workflows/PROVENANCE.md.
"""

import json
import math
import os
import re
from dataclasses import dataclass, fields
from pathlib import Path, PurePosixPath

from .backends import RestoreRequest


WORKFLOW_PATH = Path(__file__).resolve().parent.parent / "workflows" / "restore.api.json"
VIDEO_NODE_ID = "8"
REFERENCE_NODE_ID = "13"
PREVIOUS_NODE_ID = "21"
OUTPUT_NODE_ID = "20"
VIDEO_INPUT = "file"
IMAGE_INPUT = "image"
DISTILLED_SIGMAS = (1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0)

LOCAL_NODE_TYPES = frozenset({
    "UNETLoader", "CLIPLoader", "VAELoader", "LTXICLoRALoaderModelOnly",
    "CLIPTextEncode", "LTXVConditioning", "LoadVideo", "GetVideoComponents",
    "ImageScale", "EmptyLTXVLatentVideo", "LTXAddVideoICLoRAGuide", "LoadImage",
    "LTXVAddGuide", "KSamplerSelect", "ManualSigmas", "LTXVTiledFusionSampler",
    "VAEDecodeTiled", "CreateVideo", "SaveVideo",
})


def _asset_name(value: str, label: str) -> str:
    """Accept an uploaded ComfyUI-relative name, including a safe subfolder."""
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{label} must be a nonempty uploaded filename")
    path = PurePosixPath(value)
    if (path.is_absolute() or ".." in path.parts or ":" in value
            or "\\" in value or "\x00" in value or any(ord(c) < 32 for c in value)):
        raise ValueError(f"{label} must be a relative ComfyUI input name, without traversal")
    if value.endswith("/") or str(path) == ".":
        raise ValueError(f"{label} must name a file")
    return value


@dataclass(frozen=True)
class ModelFiles:
    transformer: str = "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
    text_encoder: str = "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
    video_vae: str = "ltx-2.5-video-vae-conv-bf16.safetensors"
    restore_lora: str = "ltx-2.5-22b-ic-lora-restore-1.0.safetensors"

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "ModelFiles":
        from dotenv import dotenv_values

        defaults = cls()
        env = dotenv_values(env_file or WORKFLOW_PATH.parent.parent / ".env")
        return cls(**{
            field.name: os.environ.get(f"FACETRUE_{field.name.upper()}")
            or env.get(f"FACETRUE_{field.name.upper()}") or getattr(defaults, field.name)
            for field in fields(cls)
        })

    def validate(self) -> None:
        for field in fields(self):
            name = _asset_name(getattr(self, field.name), field.name)
            if not name.endswith(".safetensors"):
                raise ValueError(f"{field.name} must be a local .safetensors model filename")


def _validate_request(request: RestoreRequest) -> None:
    if isinstance(request.steps, bool) or request.steps != 8:
        raise ValueError("LTX-2.5 distilled Restore requires the fixed 8-step sigma schedule")
    if (not isinstance(request.seed, int) or isinstance(request.seed, bool)
            or not 0 <= request.seed < 2**32):
        raise ValueError("seed must be an integer between 0 and 2**32 - 1")
    for name in ("width", "height"):
        size = getattr(request, name)
        if not isinstance(size, int) or isinstance(size, bool) or not 64 <= size <= 4096 or size % 32:
            raise ValueError(f"{name} must be a multiple of 32 between 64 and 4096")
    length = request.frame_count
    if (not isinstance(length, int) or isinstance(length, bool) or not 1 <= length <= 97
            or (length - 1) % 8):
        raise ValueError("frame_count must be 8*n+1 and at most 97; split longer clips first")
    if (not isinstance(request.fps, (int, float)) or isinstance(request.fps, bool)
            or not math.isfinite(request.fps) or not 1 <= request.fps <= 120):
        raise ValueError("fps must be finite and between 1 and 120")
    if request.previous_frames is not None and length < 17:
        raise ValueError("A chained window must accommodate its 17-frame prefix")
    if not isinstance(request.prompt, str) or not isinstance(request.negative_prompt, str):
        raise ValueError("Prompts must be strings")


def validate_graph(graph: dict) -> None:
    """Reject closed/API nodes, broken links, and cycles before queueing a graph."""
    dependencies = {}
    if not graph or OUTPUT_NODE_ID not in graph:
        raise ValueError("Workflow has no SaveVideo output")
    for node_id, node in graph.items():
        if node.get("class_type") not in LOCAL_NODE_TYPES:
            raise ValueError(f"Workflow contains an unapproved node: {node.get('class_type')}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            raise ValueError(f"Invalid inputs on node {node_id}")
        dependencies[node_id] = []
        for value in inputs.values():
            if isinstance(value, list):
                if (len(value) != 2 or value[0] not in graph
                        or not isinstance(value[1], int) or isinstance(value[1], bool) or value[1] < 0):
                    raise ValueError(f"Broken workflow link on node {node_id}")
                dependencies[node_id].append(value[0])
    visiting, visited = set(), set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ValueError("Workflow contains a dependency cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in dependencies[node_id]:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        visit(node_id)


def build_workflow(
    request: RestoreRequest,
    video_name: str,
    reference_name: str | None = None,
    previous_name: str | None = None,
    model_files: ModelFiles | None = None,
) -> dict:
    """Build one 8*n+1 frame window; assets must already be uploaded.

    ``previous_name`` contains exactly the prior restored window's last 17 frames.
    The runner verifies that count before uploading. It must be generated separately
    for each comparison arm. No-reference runs contain no photo LoadImage/guide.
    """
    _validate_request(request)
    video_name = _asset_name(video_name, "video_name")
    if (request.reference is None) != (reference_name is None):
        raise ValueError("reference_name must be supplied exactly when request.reference is set")
    if (request.previous_frames is None) != (previous_name is None):
        raise ValueError("previous_name must be supplied exactly when request.previous_frames is set")
    if reference_name is not None:
        reference_name = _asset_name(reference_name, "reference_name")
    if previous_name is not None:
        previous_name = _asset_name(previous_name, "previous_name")

    models = model_files or ModelFiles.from_env()
    models.validate()
    graph = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    graph["1"]["inputs"]["unet_name"] = models.transformer
    graph["2"]["inputs"]["clip_name"] = models.text_encoder
    graph["3"]["inputs"]["vae_name"] = models.video_vae
    graph["4"]["inputs"]["lora_name"] = models.restore_lora
    graph["5"]["inputs"]["text"] = request.prompt
    graph["6"]["inputs"]["text"] = request.negative_prompt
    graph["7"]["inputs"]["frame_rate"] = request.fps
    graph[VIDEO_NODE_ID]["inputs"][VIDEO_INPUT] = video_name
    for node_id in ("10", "11"):
        graph[node_id]["inputs"].update(width=request.width, height=request.height)
    graph["11"]["inputs"]["length"] = request.frame_count
    graph["16"]["inputs"]["sigmas"] = ", ".join(str(x) for x in DISTILLED_SIGMAS)

    last_guide = "12"
    if previous_name is not None:
        graph[PREVIOUS_NODE_ID] = {"class_type": "LoadVideo", "inputs": {VIDEO_INPUT: previous_name}}
        graph["22"] = {"class_type": "GetVideoComponents", "inputs": {"video": [PREVIOUS_NODE_ID, 0]}}
        graph["23"] = {
            "class_type": "LTXVAddGuide",
            "inputs": {"positive": [last_guide, 0], "negative": [last_guide, 1],
                       "latent": [last_guide, 2], "vae": ["3", 0], "image": ["22", 0],
                       "frame_idx": 0, "strength": 1.0},
        }
        last_guide = "23"
    if reference_name is not None:
        graph[REFERENCE_NODE_ID]["inputs"][IMAGE_INPUT] = reference_name
        graph["14"]["inputs"].update(
            positive=[last_guide, 0], negative=[last_guide, 1], latent=[last_guide, 2],
        )
        last_guide = "14"
    else:
        del graph[REFERENCE_NODE_ID]
        del graph["14"]
    graph["17"]["inputs"].update(
        positive=[last_guide, 0], negative=[last_guide, 1], latents=[last_guide, 2], seed=request.seed,
    )
    graph["19"]["inputs"]["fps"] = request.fps
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", request.output.stem)[:80] or "restore"
    graph[OUTPUT_NODE_ID]["inputs"]["filename_prefix"] = f"facetrue/{stem}"
    validate_graph(graph)
    return graph
