#!/usr/bin/env python3
"""Run the real three-arm synthetic-degradation pilot; never scores mock output."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def run(args):
    from app.backends import get_backend
    from app.config import Settings
    from app.evaluation import evaluate_experiment

    settings = Settings()
    backend = get_backend(settings)
    adapter = None
    if not args.direct:
        from app.pipeline import restore_video

        async def adapter(request, active_backend):
            per_request = settings.model_copy(update={
                "width": request.width, "height": request.height, "fps": request.fps,
                "steps": request.steps,
            })
            return await restore_video(
                request.video, request.reference, request.output, active_backend, per_request,
                seed=request.seed, negative_prompt=request.negative_prompt, prompt=request.prompt,
            )

    report = await evaluate_experiment(
        args.manifest, args.output, backend=backend, model_dir=args.model_dir,
        backend_mode=settings.mode, render_adapter=adapter, ffmpeg=settings.ffmpeg,
    )
    print("clip_id,correct_minus_without,correct_minus_wrong,status")
    for clip in report["clips"]:
        delta = clip["report"]["paired_deltas"]
        print(f"{clip['id']},{delta['correct_minus_without']},{delta['correct_minus_wrong']},{clip['status']}")
    print(json.dumps({"output": str(args.output.resolve()), "evidence_kind": report["evidence_kind"],
                      "note": "Pilot diagnostic; inspect coverage and all three videos."}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New empty directory; outputs are private and gitignored")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models" / "evaluation")
    parser.add_argument("--direct", action="store_true", help="49/97-frame hardware preflight without chunk adapter")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as error:
        parser.exit(2, f"Evaluation failed: {error}\n")


if __name__ == "__main__":
    main()
