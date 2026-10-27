#!/usr/bin/env python3
"""Run a local paired comparison. Paths and outputs stay on your computer."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backends import get_backend
from app.config import Settings
from app.media import PRESETS, normalize_video
from app.pipeline import run_comparison
from app.reference import BBox, build_reference_canvas


def box(value: str) -> BBox:
    try:
        return BBox(*(int(v) for v in value.split(",")))
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("Use x,y,width,height in normalized output pixels") from exc


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--photo", type=Path, required=True)
    parser.add_argument("--bbox", type=box, required=True)
    parser.add_argument("--photo-bbox", type=box)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--deinterlace", action="store_true")
    parser.add_argument("--synthetic", action="store_true", help="Burn in synthetic-test disclosure on comparison exports")
    parser.add_argument("--preset", choices=PRESETS, default="neutral")
    args = parser.parse_args()
    settings = Settings()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Output directory must be empty")
    args.output.mkdir(parents=True, exist_ok=True)
    normal = args.output / "normalized.mp4"
    normalize_video(args.video, normal, settings.width, settings.height, settings.fps,
                    args.deinterlace, settings.max_seconds, settings.ffmpeg, settings.ffprobe)
    canvas = build_reference_canvas(args.photo, args.output / "reference.png", args.bbox,
                                    settings.width, settings.height, args.photo_bbox)
    print(json.dumps({"mode": settings.mode, "crop_method": canvas.crop_method}))
    result = await run_comparison(normal, canvas.path, args.output / "comparison", get_backend(settings), settings,
                                  args.seed, args.preset, args.synthetic,
                                  lambda value, message: print(f"{value:.0%} {message}", flush=True))
    print(json.dumps({key: str(path) for key, path in result.items()}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
