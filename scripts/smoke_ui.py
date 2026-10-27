#!/usr/bin/env python3
"""Optional real-browser smoke. Uses synthetic inputs and a fresh browser profile."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-executable", required=True)
    args = parser.parse_args()
    support = ROOT / "_support" / "browser-smoke"
    support.mkdir(parents=True, exist_ok=True)
    clip, photo = support / "synthetic.mp4", support / "synthetic-photo.png"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=256x256:rate=24", "-t", "4", "-c:v", "libx264", str(clip)], check=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=coral:size=128x128", "-frames:v", "1", "-update", "1", str(photo)], check=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "FACETRUE_MODE": "mock", "FACETRUE_WIDTH": "256", "FACETRUE_HEIGHT": "256",
           "FACETRUE_DATA_DIR": str(support / "data")}
    url = f"http://127.0.0.1:{port}"
    with (support / "server.log").open("w") as log:
        server = subprocess.Popen([str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "app.main:app",
                                   "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Test app did not start")
            errors = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=args.browser_executable, headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url, wait_until="networkidle")
                page.locator("#mockNotice").wait_for(state="visible")
                page.screenshot(path=str(support / "desktop.png"), full_page=True)
                page.locator("#videoInput").set_input_files(str(clip))
                page.locator("#frameCanvas").wait_for(state="visible", timeout=30000)
                page.locator("#frameCanvas").click(position={"x": 100, "y": 100})
                page.locator("#photoInput").set_input_files(str(photo))
                page.locator("#referencePreview").wait_for(state="visible", timeout=30000)
                page.locator("#synthetic").check()
                page.locator("#runButton").click()
                page.locator("#resultsSection").wait_for(state="visible", timeout=60000)
                page.locator("#resultMockBadge").wait_for(state="visible")
                page.locator("#syntheticBadge").wait_for(state="visible")
                page.wait_for_function("!document.querySelector('#playButton').disabled")
                page.locator("#playButton").click()
                page.wait_for_function("document.querySelector('#originalVideo').currentTime > .25")
                page.locator("#playButton").click()
                page.locator("#scrubber").evaluate("el => { el.value = '1.5'; el.dispatchEvent(new Event('input', {bubbles:true})); }")
                page.wait_for_function("[...document.querySelectorAll('.comparison-card video')].every(v => !v.seeking && Math.abs(v.currentTime - 1.5) < .002) && !document.querySelector('#playButton').disabled")
                page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                page.locator("#resultsSection").screenshot(path=str(support / "comparison.png"))
                with page.expect_download() as event:
                    page.locator("#downloadSideBySide").click()
                download = event.value
                assert download.failure() is None
                download.save_as(str(support / "downloaded-comparison.mp4"))
                page.locator("#wipeTab").click()
                page.locator("#wipeVideo").wait_for(state="visible")
                page.reload(wait_until="networkidle")
                page.locator("#resultsSection").wait_for(state="visible", timeout=15000)
                mobile = context.new_page()
                mobile.set_viewport_size({"width": 390, "height": 844})
                mobile.goto(url, wait_until="networkidle")
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.screenshot(path=str(support / "mobile.png"), full_page=True)
                assert not errors, errors
                context.close()
                browser.close()
            summary = {"status": "passed", "mode": "mock", "inputs": "synthetic color patterns",
                       "checks": ["upload", "face selection", "photo", "canvas", "job", "3-way playback",
                                  "same-time scrub", "MP4 download", "wipe", "reload resume", "mobile overflow"],
                       "browser_errors": errors, "gpu_inference_verified": False}
            (support / "result.json").write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
