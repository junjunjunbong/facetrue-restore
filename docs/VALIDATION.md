# Validation record

This record separates software verification from model-quality evidence.
No successful LTX GPU restoration or measured identity improvement is recorded.

## Completed on the development Mac

| Check | Observed result | What it establishes |
|---|---|---|
| Python suite | 87 passed, plus 20 unittest subtests | Offline workflow/configuration, geometry, frame accounting, FFmpeg processing, SDK error handling, API flow and evaluation safeguards |
| Static checks | Ruff, Python compilation and JavaScript syntax passed | The checked source parses and passes the configured lint rules |
| Browser smoke | Chrome on macOS, isolated profile, synthetic inputs | Upload → face selection → photo → reference canvas → mock job → synchronized player → MP4 download |
| Player seek | All three displayed frames checked at 1.5 seconds | Seeking waits for all video elements to finish; same-frame pause/scrub in the smoke input |
| Browser recovery/mobile | Reload recovery passed; 390px viewport had no horizontal overflow | The tested UI states fit and resume their persisted job |
| Browser JavaScript | No page errors in the smoke flow | The tested frontend flow ran without unhandled page exceptions |
| Real SDK package | `comfy-sdk==0.5.0` parsed the local API graph; environment restored | Installed SDK interface compatibility before network inference |
| Real proxy package | `comfy-api-proxy==0.1.6` launcher served loopback HTTP health | Proxy startup works; this does not establish GPU connectivity |
| Evaluation weights | YuNet/SFace downloads matched pinned SHA256 and sizes | The intended public evaluation files were retrieved; weights remain gitignored |
| CPU evaluation-model smoke | Blank image returned `no_face`; SFace forward returned a finite 128-dimensional embedding | Both ONNX models load and execute; no identity or restoration score was measured |
| Installation | Default and `--comfy` setup paths completed against the locked requirements | The tested Mac environment can install the app and optional client dependencies |

Python was 3.11.15. Exact package versions are in `requirements-lock.txt` and
`requirements-comfy-lock.txt`. The suite currently emits one upstream Starlette
TestClient/httpx deprecation warning; tests still pass. It is not suppressed.

Browser smoke uses color-pattern video and a solid-color image. These fixtures
are **not** family footage, photographs of a person, or restoration-quality
examples. Its outputs and screenshots are local under `_support/browser-smoke/`
and excluded from git. The mock videos themselves visibly identify input copies.

Reproduce the ordinary tests with:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests scripts
```

The optional browser smoke needs Playwright and an existing Chrome/Chromium
executable. It launches a fresh profile and its own test server:

```bash
python scripts/smoke_ui.py \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

Run that command in the environment where Playwright is installed. The app's
`.venv` must already exist. No normal browser profile or signed-in session is used.

## Still unverified

- GPU-PC endpoint and installed source/model environment. The Mac had no `.env`
  or `COMFYUI_URL` configured during this development run.
- LTX 49-frame and 97-frame completion on the RTX 5090.
- A real ten-second 97/17 chained restoration.
- Peak GPU memory, GPU-PC RAM, loading time, sampling time and decoding time.
- Three real controlled clips showing the correct-photo effect, with wrong-photo
  controls, detector coverage and visual review.
- Identity fidelity, temporal seam quality, color accuracy or historical truth.
- An actual final demo recording and submission URLs.

Use [GPU_PREFLIGHT.md](GPU_PREFLIGHT.md) for the next checks and
[EVALUATION.md](EVALUATION.md) for the controlled experiment. The project's
continuation gate in [PLAN.md](PLAN.md) remains open until those results exist.
No mock output or unit-test fixture should be used to fill that gate.
