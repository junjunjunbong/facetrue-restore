#!/usr/bin/env python3
"""Explicit, hash-checked download of optional evaluation weights and licenses."""

import argparse
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.evaluation import MODEL_SPECS, verify_model


def download(model_dir: Path) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    for key, spec in MODEL_SPECS.items():
        target = model_dir / spec["filename"]
        if target.exists():
            verify_model(target, key)
        else:
            with tempfile.NamedTemporaryFile(dir=model_dir, prefix=f".{key}-", suffix=".part", delete=False) as stream:
                temporary = Path(stream.name)
            try:
                with urllib.request.urlopen(spec["url"], timeout=30) as response, temporary.open("wb") as stream:
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > spec["bytes"]:
                            raise ValueError(f"Oversized {key} download")
                        stream.write(chunk)
                verify_model(temporary, key)
                if target.exists():
                    raise FileExistsError(target)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        license_url = spec["license_url"].replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/blob/", "/")
        license_path = model_dir / f"LICENSE-{key}.txt"
        if not license_path.exists():
            with urllib.request.urlopen(license_url, timeout=30) as response:
                text = response.read(100_000).decode("utf-8")
            expected = "MIT License" if key == "yunet" else "Apache License"
            if expected not in text:
                raise ValueError(f"Unexpected license response: {license_url}")
            license_path.write_text(text, encoding="utf-8")
        print(f"Verified {target.name}: {spec['sha256']} ({spec['license']})")
    print("SFace exact training-data provenance is unconfirmed; see docs/EVALUATION.md.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models" / "evaluation")
    args = parser.parse_args()
    try:
        download(args.model_dir)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Model download failed: {error}\n")
